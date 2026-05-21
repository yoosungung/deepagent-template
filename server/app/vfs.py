import datetime
import base64
import logging
from typing import Any, Optional, Sequence
from datetime import timezone

from deepagents.backends.protocol import (
    BackendProtocol, LsResult, ReadResult, WriteResult, EditResult,
    GrepResult, GlobResult, FileUploadResponse, FileDownloadResponse,
    FileInfo, FileData, FileOperationError, GrepMatch,
    FILE_NOT_FOUND, IS_DIRECTORY, PERMISSION_DENIED
)
from deepagents.backends.utils import (
    create_file_data, update_file_data, file_data_to_string,
    perform_string_replacement, grep_matches_from_files,
    _glob_search_files, slice_read_response, _get_file_type
)
import psycopg
from psycopg.rows import dict_row
from app.database import get_sync_pool, get_async_pool

logger = logging.getLogger(__name__)

class PostgresVFSBackend(BackendProtocol):
    """PostgreSQL-backed Virtual File System (VFS) implementation for DeepAgents."""

    def __init__(self):
        super().__init__()
        # Retrieve pools
        self.sync_pool = get_sync_pool()
        self.async_pool = get_async_pool()

    def _prepare_file_dict(self, rows) -> dict[str, FileData]:
        files: dict[str, FileData] = {}
        for row in rows:
            files[row["path"]] = FileData(
                content=row["content"],
                encoding=row["encoding"] or "utf-8",
                created_at=row["created_at"].isoformat() if row["created_at"] else None,
                modified_at=row["modified_at"].isoformat() if row["modified_at"] else None
            )
        return files

    # --- Sync Methods ---

    def ls(self, path: str) -> LsResult:
        logger.debug("VFS ls: %s", path)
        if not path.startswith("/"):
            return LsResult(error="Path must start with '/'")
        
        normalized_path = path if path.endswith("/") else path + "/"
        
        try:
            with self.sync_pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    # Query all paths matching prefix
                    cur.execute(
                        "SELECT path, is_dir, size, modified_at FROM vfs_files WHERE path LIKE %s ORDER BY path;",
                        (f"{normalized_path}%",)
                    )
                    rows = cur.fetchall()
            
            infos: list[FileInfo] = []
            subdirs: set[str] = set()

            for row in rows:
                k = row["path"]
                if k == path:
                    continue
                
                # Get the relative path after the directory
                relative = k[len(normalized_path) :]
                
                # If relative path contains '/', it's in a subdirectory
                if "/" in relative:
                    subdir_name = relative.split("/")[0]
                    subdirs.add(normalized_path + subdir_name + "/")
                    continue
                
                infos.append(
                    FileInfo(
                        path=k,
                        is_dir=row["is_dir"],
                        size=row["size"] or 0,
                        modified_at=row["modified_at"].isoformat() if row["modified_at"] else ""
                    )
                )
            
            # Add unique directories
            for subdir in sorted(subdirs):
                # Check modified time if directory already in db, else empty
                infos.append(FileInfo(path=subdir, is_dir=True, size=0, modified_at=""))
            
            infos.sort(key=lambda x: x.get("path", ""))
            return LsResult(entries=infos)
            
        except Exception as e:
            logger.error("VFS ls error: %s", e, exc_info=True)
            return LsResult(error=str(e))

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        logger.debug("VFS read: %s (offset=%d, limit=%d)", file_path, offset, limit)
        try:
            with self.sync_pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT path, content, encoding, is_dir, created_at, modified_at FROM vfs_files WHERE path = %s;",
                        (file_path,)
                    )
                    row = cur.fetchone()
            
            if not row:
                return ReadResult(error=f"File '{file_path}' not found")
            
            if row["is_dir"]:
                return ReadResult(error=f"'{file_path}' is a directory")

            file_data = FileData(
                content=row["content"],
                encoding=row["encoding"] or "utf-8",
                created_at=row["created_at"].isoformat() if row["created_at"] else None,
                modified_at=row["modified_at"].isoformat() if row["modified_at"] else None
            )

            if _get_file_type(file_path) != "text":
                return ReadResult(file_data=file_data)

            sliced = slice_read_response(file_data, offset, limit)
            if isinstance(sliced, ReadResult):
                return sliced
            
            sliced_fd = FileData(
                content=sliced,
                encoding=file_data.get("encoding", "utf-8"),
            )
            if "created_at" in file_data:
                sliced_fd["created_at"] = file_data["created_at"]
            if "modified_at" in file_data:
                sliced_fd["modified_at"] = file_data["modified_at"]
            return ReadResult(file_data=sliced_fd)
            
        except Exception as e:
            logger.error("VFS read error: %s", e, exc_info=True)
            return ReadResult(error=str(e))

    def write(self, file_path: str, content: str, overwrite: bool = False) -> WriteResult:
        logger.debug("VFS write: %s (overwrite=%s)", file_path, overwrite)
        try:
            with self.sync_pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    if not overwrite:
                        # Check if exists
                        cur.execute("SELECT count(*) FROM vfs_files WHERE path = %s;", (file_path,))
                        if cur.fetchone()["count"] > 0:
                            return WriteResult(error=f"Cannot write to {file_path} because it already exists.")
                    
                    # Insert with ON CONFLICT DO UPDATE (Upsert)
                    size = len(content)
                    cur.execute(
                        """
                        INSERT INTO vfs_files (path, content, is_dir, size, modified_at)
                        VALUES (%s, %s, FALSE, %s, NOW())
                        ON CONFLICT (path) DO UPDATE
                        SET content = EXCLUDED.content, size = EXCLUDED.size, modified_at = NOW();
                        """,
                        (file_path, content, size)
                    )
                    conn.commit()
            return WriteResult(path=file_path)
        except Exception as e:
            logger.error("VFS write error: %s", e, exc_info=True)
            return WriteResult(error=str(e))

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        logger.debug("VFS edit: %s", file_path)
        try:
            with self.sync_pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT content, encoding, created_at, modified_at FROM vfs_files WHERE path = %s AND is_dir = FALSE;", (file_path,))
                    row = cur.fetchone()
                    if not row:
                        return EditResult(error=f"Error: File '{file_path}' not found")
                    
                    file_data = FileData(
                        content=row["content"],
                        encoding=row["encoding"] or "utf-8",
                        created_at=row["created_at"].isoformat() if row["created_at"] else None,
                        modified_at=row["modified_at"].isoformat() if row["modified_at"] else None
                    )
                    content = file_data_to_string(file_data)
                    result = perform_string_replacement(content, old_string, new_string, replace_all)
                    
                    if isinstance(result, str):
                        return EditResult(error=result)
                    
                    new_content, occurrences = result
                    size = len(new_content)
                    cur.execute(
                        "UPDATE vfs_files SET content = %s, size = %s, modified_at = NOW() WHERE path = %s;",
                        (new_content, size, file_path)
                    )
                    conn.commit()
            return EditResult(path=file_path, occurrences=int(occurrences))
        except Exception as e:
            logger.error("VFS edit error: %s", e, exc_info=True)
            return EditResult(error=str(e))

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult:
        logger.debug("VFS grep: %s", pattern)
        try:
            search_dir = path if path is not None else "/"
            with self.sync_pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    # Optimize search: only load files matching the substring pattern or base64 files
                    cur.execute(
                        """
                        SELECT path, content, encoding, created_at, modified_at 
                        FROM vfs_files 
                        WHERE is_dir = FALSE 
                          AND path LIKE %s 
                          AND (encoding = 'base64' OR content LIKE %s);
                        """,
                        (f"{search_dir}%", f"%{pattern}%")
                    )
                    rows = cur.fetchall()
            
            files = self._prepare_file_dict(rows)
            return grep_matches_from_files(files, pattern, search_dir, glob)
        except Exception as e:
            logger.error("VFS grep error: %s", e, exc_info=True)
            return GrepResult(error=str(e))

    def glob(self, pattern: str, path: str = "/") -> GlobResult:
        logger.debug("VFS glob: %s in %s", pattern, path)
        try:
            with self.sync_pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT path, content, encoding, created_at, modified_at FROM vfs_files WHERE is_dir = FALSE AND path LIKE %s;",
                        (f"{path}%",)
                    )
                    rows = cur.fetchall()
            
            files = self._prepare_file_dict(rows)
            result = _glob_search_files(files, pattern, path)
            if result == "No files found" or not result.strip():
                return GlobResult(matches=[])
            
            paths = result.split("\n")
            infos: list[FileInfo] = []
            for p in paths:
                if not p:
                    continue
                fd = files.get(p)
                size = len(fd.get("content", "")) if fd else 0
                infos.append(
                    FileInfo(
                        path=p,
                        is_dir=False,
                        size=size,
                        modified_at=fd.get("modified_at", "") if fd else ""
                    )
                )
            return GlobResult(matches=infos)
        except Exception as e:
            logger.error("VFS glob error: %s", e, exc_info=True)
            return GlobResult(error=str(e))

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        logger.debug("VFS upload_files")
        responses: list[FileUploadResponse] = []
        try:
            with self.sync_pool.connection() as conn:
                with conn.cursor() as cur:
                    for path, content in files:
                        try:
                            # Try to decode as text, otherwise base64
                            try:
                                text_content = content.decode("utf-8")
                                encoding = "utf-8"
                            except UnicodeDecodeError:
                                text_content = base64.b64encode(content).decode("ascii")
                                encoding = "base64"
                            
                            size = len(text_content)
                            cur.execute(
                                """
                                INSERT INTO vfs_files (path, content, encoding, is_dir, size, modified_at)
                                VALUES (%s, %s, %s, FALSE, %s, NOW())
                                ON CONFLICT (path) DO UPDATE
                                SET content = EXCLUDED.content, encoding = EXCLUDED.encoding, size = EXCLUDED.size, modified_at = NOW();
                                """,
                                (path, text_content, encoding, size)
                            )
                            responses.append(FileUploadResponse(path=path, error=None))
                        except Exception as file_err:
                            responses.append(FileUploadResponse(path=path, error=str(file_err)))
                    conn.commit()
            return responses
        except Exception as e:
            logger.error("VFS upload error: %s", e, exc_info=True)
            return [FileUploadResponse(path=p, error=str(e)) for p, _ in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        logger.debug("VFS download_files")
        responses: list[FileDownloadResponse] = []
        try:
            with self.sync_pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    for path in paths:
                        cur.execute("SELECT content, encoding, is_dir FROM vfs_files WHERE path = %s;", (path,))
                        row = cur.fetchone()
                        if not row:
                            responses.append(FileDownloadResponse(path=path, content=None, error=FILE_NOT_FOUND))
                            continue
                        if row["is_dir"]:
                            responses.append(FileDownloadResponse(path=path, content=None, error=IS_DIRECTORY))
                            continue
                        
                        content_str = row["content"]
                        encoding = row["encoding"] or "utf-8"
                        try:
                            if encoding == "utf-8":
                                content_bytes = content_str.encode("utf-8")
                            else:
                                content_bytes = base64.b64decode(content_str)
                            responses.append(FileDownloadResponse(path=path, content=content_bytes, error=None))
                        except Exception as decode_err:
                            responses.append(FileDownloadResponse(path=path, content=None, error=str(decode_err)))
            return responses
        except Exception as e:
            logger.error("VFS download error: %s", e, exc_info=True)
            return [FileDownloadResponse(path=p, content=None, error=str(e)) for p in paths]

    # --- Async Methods ---

    async def als(self, path: str) -> LsResult:
        logger.debug("VFS als: %s", path)
        if not path.startswith("/"):
            return LsResult(error="Path must start with '/'")
        
        normalized_path = path if path.endswith("/") else path + "/"
        
        try:
            async with self.async_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "SELECT path, is_dir, size, modified_at FROM vfs_files WHERE path LIKE %s ORDER BY path;",
                        (f"{normalized_path}%",)
                    )
                    rows = await cur.fetchall()
            
            infos: list[FileInfo] = []
            subdirs: set[str] = set()

            for row in rows:
                k = row["path"]
                if k == path:
                    continue
                
                relative = k[len(normalized_path) :]
                if "/" in relative:
                    subdir_name = relative.split("/")[0]
                    subdirs.add(normalized_path + subdir_name + "/")
                    continue
                
                infos.append(
                    FileInfo(
                        path=k,
                        is_dir=row["is_dir"],
                        size=row["size"] or 0,
                        modified_at=row["modified_at"].isoformat() if row["modified_at"] else ""
                    )
                )
            
            for subdir in sorted(subdirs):
                infos.append(FileInfo(path=subdir, is_dir=True, size=0, modified_at=""))
            
            infos.sort(key=lambda x: x.get("path", ""))
            return LsResult(entries=infos)
        except Exception as e:
            logger.error("VFS als error: %s", e, exc_info=True)
            return LsResult(error=str(e))

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        logger.debug("VFS aread: %s", file_path)
        try:
            async with self.async_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "SELECT path, content, encoding, is_dir, created_at, modified_at FROM vfs_files WHERE path = %s;",
                        (file_path,)
                    )
                    row = await cur.fetchone()
            
            if not row:
                return ReadResult(error=f"File '{file_path}' not found")
            
            if row["is_dir"]:
                return ReadResult(error=f"'{file_path}' is a directory")

            file_data = FileData(
                content=row["content"],
                encoding=row["encoding"] or "utf-8",
                created_at=row["created_at"].isoformat() if row["created_at"] else None,
                modified_at=row["modified_at"].isoformat() if row["modified_at"] else None
            )

            if _get_file_type(file_path) != "text":
                return ReadResult(file_data=file_data)

            sliced = slice_read_response(file_data, offset, limit)
            if isinstance(sliced, ReadResult):
                return sliced
            
            sliced_fd = FileData(
                content=sliced,
                encoding=file_data.get("encoding", "utf-8"),
            )
            if "created_at" in file_data:
                sliced_fd["created_at"] = file_data["created_at"]
            if "modified_at" in file_data:
                sliced_fd["modified_at"] = file_data["modified_at"]
            return ReadResult(file_data=sliced_fd)
        except Exception as e:
            logger.error("VFS aread error: %s", e, exc_info=True)
            return ReadResult(error=str(e))

    async def awrite(self, file_path: str, content: str, overwrite: bool = False) -> WriteResult:
        logger.debug("VFS awrite: %s (overwrite=%s)", file_path, overwrite)
        try:
            async with self.async_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    if not overwrite:
                        await cur.execute("SELECT count(*) FROM vfs_files WHERE path = %s;", (file_path,))
                        row = await cur.fetchone()
                        if row["count"] > 0:
                            return WriteResult(error=f"Cannot write to {file_path} because it already exists.")
                    
                    # Insert with ON CONFLICT DO UPDATE (Upsert)
                    size = len(content)
                    await cur.execute(
                        """
                        INSERT INTO vfs_files (path, content, is_dir, size, modified_at)
                        VALUES (%s, %s, FALSE, %s, NOW())
                        ON CONFLICT (path) DO UPDATE
                        SET content = EXCLUDED.content, size = EXCLUDED.size, modified_at = NOW();
                        """,
                        (file_path, content, size)
                    )
            return WriteResult(path=file_path)
        except Exception as e:
            logger.error("VFS awrite error: %s", e, exc_info=True)
            return WriteResult(error=str(e))

    async def aedit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        logger.debug("VFS aedit: %s", file_path)
        try:
            async with self.async_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute("SELECT content, encoding, created_at, modified_at FROM vfs_files WHERE path = %s AND is_dir = FALSE;", (file_path,))
                    row = await cur.fetchone()
                    if not row:
                        return EditResult(error=f"Error: File '{file_path}' not found")
                    
                    file_data = FileData(
                        content=row["content"],
                        encoding=row["encoding"] or "utf-8",
                        created_at=row["created_at"].isoformat() if row["created_at"] else None,
                        modified_at=row["modified_at"].isoformat() if row["modified_at"] else None
                    )
                    content = file_data_to_string(file_data)
                    result = perform_string_replacement(content, old_string, new_string, replace_all)
                    
                    if isinstance(result, str):
                        return EditResult(error=result)
                    
                    new_content, occurrences = result
                    size = len(new_content)
                    await cur.execute(
                        "UPDATE vfs_files SET content = %s, size = %s, modified_at = NOW() WHERE path = %s;",
                        (new_content, size, file_path)
                    )
            return EditResult(path=file_path, occurrences=int(occurrences))
        except Exception as e:
            logger.error("VFS aedit error: %s", e, exc_info=True)
            return EditResult(error=str(e))

    async def agrep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult:
        logger.debug("VFS agrep: %s", pattern)
        try:
            search_dir = path if path is not None else "/"
            async with self.async_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    # Optimize search: only load files matching the substring pattern or base64 files
                    await cur.execute(
                        """
                        SELECT path, content, encoding, created_at, modified_at 
                        FROM vfs_files 
                        WHERE is_dir = FALSE 
                          AND path LIKE %s 
                          AND (encoding = 'base64' OR content LIKE %s);
                        """,
                        (f"{search_dir}%", f"%{pattern}%")
                    )
                    rows = await cur.fetchall()
            
            files = self._prepare_file_dict(rows)
            return grep_matches_from_files(files, pattern, search_dir, glob)
        except Exception as e:
            logger.error("VFS agrep error: %s", e, exc_info=True)
            return GrepResult(error=str(e))

    async def aglob(self, pattern: str, path: str = "/") -> GlobResult:
        logger.debug("VFS aglob: %s", pattern)
        try:
            async with self.async_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "SELECT path, content, encoding, created_at, modified_at FROM vfs_files WHERE is_dir = FALSE AND path LIKE %s;",
                        (f"{path}%",)
                    )
                    rows = await cur.fetchall()
            
            files = self._prepare_file_dict(rows)
            result = _glob_search_files(files, pattern, path)
            if result == "No files found" or not result.strip():
                return GlobResult(matches=[])
            
            paths = result.split("\n")
            infos: list[FileInfo] = []
            for p in paths:
                if not p:
                    continue
                fd = files.get(p)
                size = len(fd.get("content", "")) if fd else 0
                infos.append(
                    FileInfo(
                        path=p,
                        is_dir=False,
                        size=size,
                        modified_at=fd.get("modified_at", "") if fd else ""
                    )
                )
            return GlobResult(matches=infos)
        except Exception as e:
            logger.error("VFS aglob error: %s", e, exc_info=True)
            return GlobResult(error=str(e))

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        logger.debug("VFS aupload_files")
        responses: list[FileUploadResponse] = []
        try:
            async with self.async_pool.connection() as conn:
                async with conn.cursor() as cur:
                    for path, content in files:
                        try:
                            try:
                                text_content = content.decode("utf-8")
                                encoding = "utf-8"
                            except UnicodeDecodeError:
                                text_content = base64.b64encode(content).decode("ascii")
                                encoding = "base64"
                            
                            size = len(text_content)
                            await cur.execute(
                                """
                                INSERT INTO vfs_files (path, content, encoding, is_dir, size, modified_at)
                                VALUES (%s, %s, %s, FALSE, %s, NOW())
                                ON CONFLICT (path) DO UPDATE
                                SET content = EXCLUDED.content, encoding = EXCLUDED.encoding, size = EXCLUDED.size, modified_at = NOW();
                                """,
                                (path, text_content, encoding, size)
                            )
                            responses.append(FileUploadResponse(path=path, error=None))
                        except Exception as file_err:
                            responses.append(FileUploadResponse(path=path, error=str(file_err)))
            return responses
        except Exception as e:
            logger.error("VFS aupload error: %s", e, exc_info=True)
            return [FileUploadResponse(path=p, error=str(e)) for p, _ in files]

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        logger.debug("VFS adownload_files")
        responses: list[FileDownloadResponse] = []
        try:
            async with self.async_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    for path in paths:
                        await cur.execute("SELECT content, encoding, is_dir FROM vfs_files WHERE path = %s;", (path,))
                        row = await cur.fetchone()
                        if not row:
                            responses.append(FileDownloadResponse(path=path, content=None, error=FILE_NOT_FOUND))
                            continue
                        if row["is_dir"]:
                            responses.append(FileDownloadResponse(path=path, content=None, error=IS_DIRECTORY))
                            continue
                        
                        content_str = row["content"]
                        encoding = row["encoding"] or "utf-8"
                        try:
                            if encoding == "utf-8":
                                content_bytes = content_str.encode("utf-8")
                            else:
                                content_bytes = base64.b64decode(content_str)
                            responses.append(FileDownloadResponse(path=path, content=content_bytes, error=None))
                        except Exception as decode_err:
                            responses.append(FileDownloadResponse(path=path, content=None, error=str(decode_err)))
            return responses
        except Exception as e:
            logger.error("VFS adownload error: %s", e, exc_info=True)
            return [FileDownloadResponse(path=p, content=None, error=str(e)) for p in paths]
