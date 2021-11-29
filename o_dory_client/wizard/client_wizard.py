# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import ujson as json


# wizard objects are deleted from the databaase
# after a short period of time


class ClientDataWizard(models.TransientModel):
    _name = "client.data.wizard"
    _description = "Document Data Wizard"

    wizard_id = fields.Many2one(
        "client.wizard", ondelete="cascade", string="Client Wizard", required=True
    )
    document_id = fields.Integer("Document ID")  # this is used to update/remove a file
    raw_file = fields.Binary("Your File")
    filename = fields.Char(
        "Filename (Optional)",
        default="Unnamed",
        help="The filename will only be stored on the client for bookkeeping purposes. This information will not be sent to the server.",
    )
    search_term = fields.Char("Search Keyword")
    search_result = fields.Text("Search Result")


class ClientWizard(models.TransientModel):
    _name = "client.wizard"
    _description = "Client Wizard"

    data_ids = fields.One2many("client.data.wizard", "wizard_id", string="Data")

    # explicitly pass in context
    def _default_manager(self):
        return self.env["client.manager"].browse(self.env.context.get("active_id"))

    manager_id = fields.Many2one(
        "client.manager", string="O-DORY Client Manager", default=_default_manager
    )

    def action_do_upload(self):
        self.ensure_one()
        if self.data_ids:
            raw_data = self.data_ids.mapped("raw_file")
            filenames = self.data_ids.mapped("filename")
            self.manager_id.upload(list(zip(raw_data, filenames)))
        return {"type": "ir.actions.act_window_close"}

    def action_do_remove(self):
        self.ensure_one()
        if self.data_ids:
            doc_ids = self.data_ids.mapped("document_id")
            self.manager_id.remove(doc_ids)
        return {"type": "ir.actions.act_window_close"}

    def action_do_update(self):
        self.ensure_one()
        if self.data_ids:
            doc_ids = self.data_ids.mapped("document_id")
            raw_data = self.data_ids.mapped("raw_file")
            if doc_ids and raw_data and len(doc_ids) == len(raw_data):
                self.manager_id.update(doc_ids, raw_data)
        return {"type": "ir.actions.act_window_close"}

    def action_do_search(self):
        self.ensure_one()
        for data in self.data_ids:
            res = self.manager_id.search_keywords([data.search_term])
            # give a list of document ids that contains that keyword
            data.search_result = "These documents may contain '{}': {}".format(
                data.search_term, res
            )

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
        # return {"type": "ir.actions.act_window_close"}
