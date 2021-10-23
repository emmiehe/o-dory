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

    # explicitly pass in context
    def _default_account(self):
        return self.env["o.dory.account"].browse(self.env.context.get("active_id"))

    account_id = fields.Many2one(
        "o.dory.account", string="O-DORY Account", default=_default_account
    )
    document_id = fields.Integer("Document ID")  # this is used to update a file
    raw_file = fields.Binary(string="Your File")

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
        if self.raw_file is not None:
            self.account_id.upload(self.raw_file)
        return {"type": "ir.actions.act_window_close"}

    def action_do_remove(self):
        self.ensure_one()
        if self.document_id is not None:
            self.account_id.remove(self.document_id)
        return {"type": "ir.actions.act_window_close"}
