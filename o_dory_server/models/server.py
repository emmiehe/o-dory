# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# import odoo.addons.decimal_precision as dp
import json

# this class represents a physical server database/filesystem
class ServerDatabase(models.Model):
    _name = "server.database"
    _description = "Database"

    name = fields.Char("Name")
    # admin has access to a server database, for future demo usage
    user_id = fields.Many2one("res.users", string="Database Admin")
    available = fields.Boolean("Available", help="This field indicates whether a server is available for the customers (user file storage). It would not be available if this server is used for other purposes (a dedicated server), or it is a master.")


# each user has a folder on the server
class ServerFolder(models.Model):
    _name = "server.folder"
    _description = "Folder"

    name = fields.Char("Name")
    user_id = fields.Many2one("res.users", ondelete="cascade", string="User", required=1)

    @api.model_create_multi
    def create(self, vals_list):
        # when a folder is created, the partitions need to be allocated to all servers
        # for now I assume server size is fixed
        # TODO: we might need to think about expanding partitions to newly spawned servers?
        db_ids = self.env["server.database"].search([("available", "=", True)])
        if len(db_ids) < 2:
            raise ValidationError(_("Cannot create a user folder: less than two servers available."))

        res_ids = super(ServerFolder, self).create(vals_list)

        partition_data = []
        for res_id in res_ids:
            for db_id in db_ids:
                partition_data.append({
                    "name": res_id.name,
                    "folder_id": res_id.id,
                    "database_id": db_id.id
                })

        # batch create partitions, note that bitmaps are created in partition create
        self.env["server.folder.partition"].create(partition_data)
        return res_ids



# a folder will have multiple partitions,
# each partition resides in a different database
class ServerFolderPartition(models.Model):
    _name = "server.folder.partition"
    _description = "Folder Partition"

    name = fields.Char("Name")
    folder_id = fields.Many2one("server.folder", ondelete="restrict", string="Folder", required=1)
    database_id = fields.Many2one("server.database", ondelete="restrict", string="Database", required=1)
    user_id = fields.Many2one(related="folder_id.user_id")

    bitmap_version = fields.Integer("Bitmaps Version")
    bitmap_width = fields.Integer("Bitmaps Width", default=1000, readonly=1)
    bitmaps = fields.Binary("Bitmaps", attachment=False)
    # a field for display only
    bitmaps_str = fields.Char(
        "Bitmaps String", compute="_compute_bitmaps_str", store=True
    )  # this field should be removed later

    def _retrieve_column(self, encrypted_keyword, salt=None):
        for sdb in self:
            bitmaps = json.loads(sdb.bitmaps)
            index = encrypted_keyword % sdb.bitmap_width
            print("===== retrieve index is ", index)
            return json.dumps([[k, v[index]] for [k, v] in bitmaps.items()])

    @api.depends("bitmaps")
    def _compute_bitmaps_str(self):
        for sdb in self:
            dic = json.loads(sdb.bitmaps)
            string = ""
            for k, v in dic.items():
                string += "{}: {}\n".format(k, v)
            sdb.bitmaps_str = string

    @api.model_create_multi
    def create(self, vals_list):
        res_ids = super(ServerFolderPartition, self).create(vals_list)
        # when a server database is created, there should be a bitmap table setup
        for res_id in res_ids:
            res_id.bitmaps = json.dumps(dict())
        return res_ids


class EncryptedDocument(models.Model):
    _name = "encrypted.document"
    _description = "encrypted document"

    # not sure if we really need a name for the file, but keep it for now
    name = fields.Char("Name")
    blob = fields.Text("Encrypted Blob")  # maybe this should be binary
    partition_id = fields.Many2one(
        "server.folder.partition", ondelete="restrict", string="Partition"
    )
    user_id = fields.Many2one(related="partition_id.user_id")
