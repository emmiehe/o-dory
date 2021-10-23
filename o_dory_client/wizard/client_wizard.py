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
    search_result = fields.Text("Search Result")

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

    def action_do_update(self):
        self.ensure_one()
        if self.document_id is not None and self.raw_file is not None:
            self.account_id.update(self.document_id, self.raw_file)
        return {"type": "ir.actions.act_window_close"}

    def action_do_search(self):
        self.ensure_one()
        if self.search_term:
            res = self.account_id.search_keyword(self.search_term)
            # give a list of document ids that contains that keyword
            self.search_result = "search functionality not in place: {}".format(res)
            action_window = {
                "type": "ir.actions.act_window",
                "res_model": "client.wizard",
                "name": "Search Result",
                # "views": [[False, "form"]],
                "context": {"create": False},
                "res_id": self.id,
                "view_mode": "form",
                "view_id": self.env.ref("o_dory_client.wizard_client_search_result").id,
                "target": "new",
            }
            return action_window
        return {"type": "ir.actions.act_window_close"}
        # return {"type": "ir.actions.act_window_close"}

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
