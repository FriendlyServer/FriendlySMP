import os
import logging
import json
import html
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.shared.helpers import Helpers
from app.classes.shared.file_helpers import FileHelpers
from app.classes.web.base_api_handler import BaseApiHandler

logger = logging.getLogger(__name__)

files_get_schema = {
    "type": "object",
    "properties": {
        "page": {
            "type": "string",
            "minLength": 1,
            "error": "typeString",
            "fill": True,
        },
        "path": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
    },
    "additionalProperties": False,
    "minProperties": 1,
}

files_patch_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
        "contents": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
    },
    "additionalProperties": False,
    "minProperties": 1,
}

files_unzip_schema = {
    "type": "object",
    "properties": {
        "folder": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
    },
    "additionalProperties": False,
    "minProperties": 1,
}

files_create_schema = {
    "type": "object",
    "properties": {
        "parent": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
        "name": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
        "directory": {
            "type": "boolean",
            "error": "typeBool",
            "fill": True,
        },
    },
    "additionalProperties": False,
    "minProperties": 1,
}

files_rename_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
        "new_name": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
    },
    "additionalProperties": False,
    "minProperties": 1,
}

file_delete_schema = {
    "type": "object",
    "properties": {
        "filename": {
            "type": "string",
            "minLength": 5,
            "error": "typeString",
            "fill": True,
        },
    },
    "additionalProperties": False,
    "minProperties": 1,
}


class ApiServersServerFilesIndexHandler(BaseApiHandler):
    def post(self, server_id: str, backup_id=None):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if (
            EnumPermissionsServer.FILES not in server_permissions
            and EnumPermissionsServer.BACKUP not in server_permissions
        ):
            # if the user doesn't have Files or Backup permission, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )

        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )
        try:
            validate(data, files_get_schema)
        except ValidationError as e:
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": str(e),
                },
            )
        if not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            data["path"],
        ):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "TRAVERSAL DETECTED",
                    "error_data": str(e),
                },
            )
        if os.path.isdir(data["path"]):
            # TODO: limit some columns for specific permissions?
            folder = data["path"]
            return_json = {
                "root_path": {
                    "path": folder,
                    "top": data["path"]
                    == self.controller.servers.get_server_data_by_id(server_id)["path"],
                }
            }

            dir_list = []
            unsorted_files = []
            file_list = os.listdir(folder)
            for item in file_list:
                if os.path.isdir(os.path.join(folder, item)):
                    dir_list.append(item)
                else:
                    unsorted_files.append(item)
            file_list = sorted(dir_list, key=str.casefold) + sorted(
                unsorted_files, key=str.casefold
            )
            for raw_filename in file_list:
                filename = html.escape(raw_filename)
                rel = os.path.join(folder, raw_filename)
                dpath = os.path.join(folder, filename)
                if backup_id:
                    if str(
                        dpath
                    ) in self.controller.management.get_excluded_backup_dirs(backup_id):
                        if os.path.isdir(rel):
                            return_json[filename] = {
                                "path": dpath,
                                "dir": True,
                                "excluded": True,
                            }
                        else:
                            return_json[filename] = {
                                "path": dpath,
                                "dir": False,
                                "excluded": True,
                            }
                    else:
                        if os.path.isdir(rel):
                            return_json[filename] = {
                                "path": dpath,
                                "dir": True,
                                "excluded": False,
                            }
                        else:
                            return_json[filename] = {
                                "path": dpath,
                                "dir": False,
                                "excluded": False,
                            }
                else:
                    if os.path.isdir(rel):
                        return_json[filename] = {
                            "path": dpath,
                            "dir": True,
                            "excluded": False,
                        }
                    else:
                        return_json[filename] = {
                            "path": dpath,
                            "dir": False,
                            "excluded": False,
                        }
            self.finish_json(200, {"status": "ok", "data": return_json})
        else:
            try:
                with open(data["path"], encoding="utf-8") as file:
                    file_contents = file.read()
            except UnicodeDecodeError as ex:
                self.finish_json(
                    400,
                    {"status": "error", "error": "DECODE_ERROR", "error_data": str(ex)},
                )
            self.finish_json(200, {"status": "ok", "data": file_contents})

    def delete(self, server_id: str, _backup_id=None):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.FILES not in server_permissions:
            # if the user doesn't have Files permission, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )
        try:
            validate(data, file_delete_schema)
        except ValidationError as why:
            offending_key = ""
            if why.schema.get("fill", None):
                offending_key = why.path[0] if why.path else None
            err = f"""{offending_key} {self.translator.translate(
                "validators",
                why.schema.get("error"),
                self.controller.users.get_user_lang_by_id(auth_data[4]["user_id"]),
            )} {why.schema.get("enum", "")}"""
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": f"{str(err)}",
                },
            )
        if not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            data["filename"],
        ):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "TRAVERSAL DETECTED",
                    "error_data": str(e),
                },
            )

        if os.path.isdir(data["filename"]):
            proc = FileHelpers.del_dirs(data["filename"])
        else:
            proc = FileHelpers.del_file(data["filename"])
        # disabling pylint because return value could be truthy
        # but not a true boolean value
        if proc == True:  # pylint: disable=singleton-comparison
            return self.finish_json(200, {"status": "ok"})
        return self.finish_json(
            500, {"status": "error", "error": "SERVER RUNNING", "error_data": str(proc)}
        )

    def patch(self, server_id: str, _backup_id):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.FILES not in server_permissions:
            # if the user doesn't have Files permission, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )
        try:
            validate(data, files_patch_schema)
        except ValidationError as why:
            offending_key = ""
            if why.schema.get("fill", None):
                offending_key = why.path[0] if why.path else None
            err = f"""{offending_key} {self.translator.translate(
                "validators",
                why.schema.get("error"),
                self.controller.users.get_user_lang_by_id(auth_data[4]["user_id"]),
            )} {why.schema.get("enum", "")}"""
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": f"{str(err)}",
                },
            )
        if not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            data["path"],
        ):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "TRAVERSAL DETECTED",
                    "error_data": str(e),
                },
            )
        file_path = Helpers.get_os_understandable_path(data["path"])
        file_contents = data["contents"]
        # Open the file in write mode and store the content in file_object
        with open(file_path, "w", encoding="utf-8") as file_object:
            file_object.write(file_contents)
        return self.finish_json(200, {"status": "ok"})

    def put(self, server_id: str, _backup_id):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.FILES not in server_permissions:
            # if the user doesn't have Files permission, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )
        try:
            validate(data, files_create_schema)
        except ValidationError as why:
            offending_key = ""
            if why.schema.get("fill", None):
                offending_key = why.path[0] if why.path else None
            err = f"""{offending_key} {self.translator.translate(
                "validators",
                why.schema.get("error"),
                self.controller.users.get_user_lang_by_id(auth_data[4]["user_id"]),
            )} {why.schema.get("enum", "")}"""
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": f"{str(err)}",
                },
            )
        path = os.path.join(data["parent"], data["name"])
        if not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            path,
        ):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "TRAVERSAL DETECTED",
                    "error_data": str(e),
                },
            )
        if Helpers.check_path_exists(os.path.abspath(path)):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "FILE EXISTS",
                    "error_data": str(e),
                },
            )
        if data["directory"]:
            os.mkdir(path)
        else:
            # Create the file by opening it
            with open(path, "w", encoding="utf-8") as file_object:
                file_object.close()
        return self.finish_json(200, {"status": "ok"})


class ApiServersServerFilesCreateHandler(BaseApiHandler):
    def patch(self, server_id: str):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.FILES not in server_permissions:
            # if the user doesn't have Files permission, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )
        try:
            validate(data, files_rename_schema)
        except ValidationError as why:
            offending_key = ""
            if why.schema.get("fill", None):
                offending_key = why.path[0] if why.path else None
            err = f"""{offending_key} {self.translator.translate(
                "validators",
                why.schema.get("error"),
                self.controller.users.get_user_lang_by_id(auth_data[4]["user_id"]),
            )} {why.schema.get("enum", "")}"""
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": f"{str(err)}",
                },
            )
        path = data["path"]
        new_item_name = data["new_name"]
        new_item_path = os.path.join(os.path.split(path)[0], new_item_name)
        if not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            path,
        ) or not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            new_item_path,
        ):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "TRAVERSAL DETECTED",
                    "error_data": str(e),
                },
            )
        if Helpers.check_path_exists(os.path.abspath(new_item_path)):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "FILE EXISTS",
                    "error_data": {},
                },
            )

        os.rename(path, new_item_path)
        return self.finish_json(200, {"status": "ok"})

    def put(self, server_id: str):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.FILES not in server_permissions:
            # if the user doesn't have Files permission, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )
        try:
            validate(data, files_create_schema)
        except ValidationError as why:
            offending_key = ""
            if why.schema.get("fill", None):
                offending_key = why.path[0] if why.path else None
            err = f"""{offending_key} {self.translator.translate(
                "validators",
                why.schema.get("error"),
                self.controller.users.get_user_lang_by_id(auth_data[4]["user_id"]),
            )} {why.schema.get("enum", "")}"""
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": f"{str(err)}",
                },
            )
        path = os.path.join(data["parent"], data["name"])
        if not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            path,
        ):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "TRAVERSAL DETECTED",
                    "error_data": str(e),
                },
            )
        if Helpers.check_path_exists(os.path.abspath(path)):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "FILE EXISTS",
                    "error_data": str(e),
                },
            )
        if data["directory"]:
            os.mkdir(path)
        else:
            # Create the file by opening it
            with open(path, "w", encoding="utf-8") as file_object:
                file_object.close()
        return self.finish_json(200, {"status": "ok"})


class ApiServersServerFilesZipHandler(BaseApiHandler):
    def post(self, server_id: str):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.FILES not in server_permissions:
            # if the user doesn't have Files permission, return an error
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )
        try:
            validate(data, files_unzip_schema)
        except ValidationError as why:
            offending_key = ""
            if why.schema.get("fill", None):
                offending_key = why.path[0] if why.path else None
            err = f"""{offending_key} {self.translator.translate(
                "validators",
                why.schema.get("error"),
                self.controller.users.get_user_lang_by_id(auth_data[4]["user_id"]),
            )} {why.schema.get("enum", "")}"""
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": f"{str(err)}",
                },
            )
        folder = data["folder"]
        user_id = auth_data[4]["user_id"]
        if not Helpers.validate_traversal(
            self.controller.servers.get_server_data_by_id(server_id)["path"],
            folder,
        ):
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "TRAVERSAL DETECTED",
                    "error_data": str(e),
                },
            )
        if Helpers.check_file_exists(folder):
            folder = self.file_helper.unzip_file(folder, user_id)
        else:
            if user_id:
                return self.finish_json(
                    400,
                    {
                        "status": "error",
                        "error": "FILE_DOES_NOT_EXIST",
                        "error_data": str(e),
                    },
                )
        return self.finish_json(200, {"status": "ok"})
