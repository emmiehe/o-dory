# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# import odoo.addons.decimal_precision as dp
import json


class OdoryClient(models.Model):
    _name = "odory.client"
    _description = "Odory Client"

    name = fields.Char("Name")
    search_result = fields.Char("Search Result")
