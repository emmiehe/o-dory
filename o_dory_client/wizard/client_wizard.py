# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class ClientWizard(models.TransientModel):
    _name = "client.wizard"
    _description = "Client Wizard"

    # not sure we need filename
    # filename = fields.Char("Filename")

    account_id = fields.Many2one("o.dory.account", string="O-DORY Account")
    document_id = fields.Integer("Document ID") # this is used to update a file
    raw_file = fields.Binary(
        string="Your File"
    ) 
    keywords = fields.Char(
        "Keywords", help="keywords should be seperated by space"
    )  # for now this is manual, but later this should be extracted from the file

    search_term = fields.Char("Search a Keyword")

    # todo: in the future this extracts the unique words from the file
    def get_unique_keywords(self, f):
        return self.keywords.split(" ")

    def action_do_search(self):
        self.ensure_one()
        # if self.search_term:
        #     # before we do any search, we should ask the server master
        #     # (if there is one), do my partitions have the same versions bitmaps

        #     # for now I will just ask any of the replica, version conflicts should be handled later
        #     # this part should be handled with xmlrpc later, for now I query my own server
        #     partitions = self.env["server.folder.partition"].search([("user_id", "=", )])
            
        #     encrypted_search = hash(
        #         self.search_term
        #     )  # obviously this is not encrypted but it's ok for now
        #     server_database = self.env["server.database"].search(
        #         [("name", "=", "odory")], limit=1
        #     )[0]
        #     print("=====> server_database", server_database)
        #     dump = server_database._retrieve_column(encrypted_search)
        #     client = self.env["odory.client"].search([], limit=1)[0]
        #     client.search_result = ""
        #     for k, v in json.loads(dump):
        #         print("-------------->k, v", k, v)
        #         client.search_result += "{}: {}\n".format(k, v)

        return {"type": "ir.actions.act_window_close"}

    def action_do_upload(self):
        self.ensure_one()
        # if self.client_file:

        #     # prepare bitmap
        #     bitmap = [0] * 1000
        #     for keyword in self.get_unique_keywords(self.client_file):
        #         index = hash(keyword) % 1000
        #         print("=====> index", index)
        #         bitmap[index] = 1

        #     # bitmap_serialized = json.dumps(bitmap)

        #     # encrypt file
        #     # for now I skip this

        #     # send
        #     server_database = self.env["server.database"].search(
        #         [("name", "=", "odory")], limit=1
        #     )[0]
        #     print("=====> server_database", server_database)
        #     server_bitmaps = json.loads(server_database.bitmaps)
        #     # todo:  make sure filename is unique
        #     server_bitmaps[self.filename] = bitmap
        #     server_database.bitmaps = json.dumps(server_bitmaps)

        return {"type": "ir.actions.act_window_close"}
