# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class OdoryClientWizard(models.TransientModel):
    _name = "odory.client.wizard"
    _description = "odory client wizard"

    filename = fields.Char("Filename")
    client_file = fields.Binary(
        string="Upload a File"
    )  # this is the raw file from the client
    keywords = fields.Char(
        "Keywords"
    )  # for now this is manual, but later this should be extracted from the file

    search_term = fields.Char("Search Keyword")

    # secret = fields.Char(string='Secret')  # this is used to salt their words

    # todo: in the future this extracts the unique words from the file
    def get_unique_keywords(self, f):
        # f is binary
        return self.keywords.split(",")

    def action_do_search(self):
        self.ensure_one()
        if self.search_term:
            encrypted_search = hash(
                self.search_term
            )  # obvious this is not encrypted but it's ok for now
            server_database = self.env["server.database"].search(
                [("name", "=", "odory")], limit=1
            )[0]
            print("=====> server_database", server_database)
            dump = server_database._retrieve_column(encrypted_search)
            client = self.env["odory.client"].search([], limit=1)[0]
            client.search_result = ""
            for k, v in json.loads(dump):
                print("-------------->k, v", k, v)
                client.search_result += "{}: {}\n".format(k, v)

        return {"type": "ir.actions.act_window_close"}

    def action_do_upload(self):
        self.ensure_one()
        if self.client_file and self.filename:

            # prepare bitmap
            bitmap = [0] * 1000
            for keyword in self.get_unique_keywords(self.client_file):
                index = hash(keyword) % 1000
                print("=====> index", index)
                bitmap[index] = 1

            # bitmap_serialized = json.dumps(bitmap)

            # encrypt file
            # for now I skip this

            # send
            server_database = self.env["server.database"].search(
                [("name", "=", "odory")], limit=1
            )[0]
            print("=====> server_database", server_database)
            server_bitmaps = json.loads(server_database.bitmaps)
            # todo:  make sure filename is unique
            server_bitmaps[self.filename] = bitmap
            server_database.bitmaps = json.dumps(server_bitmaps)

        return {"type": "ir.actions.act_window_close"}
