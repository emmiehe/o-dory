# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
# import odoo.addons.decimal_precision as dp


class ServerDatabase(models.Model):
    _name = 'server.database'
    _description = 'server database'

    name = fields.Char('Name')
    bitmap = fields.Binary('Bitmap')

    # def action_open_scheduler_task_tree(self):
    #     self.ensure_one()
    #     action_id = self.env.ref("task_scheduler.action_scheduler_task")
    #     action_data = action_id.read()[0]
        
    #     action_data.update({
    #         'domain': [('id', 'in', self.task_ids.ids)],
    #         'context': {'default_scheduler_id': self.id}
    #     })
        
    #     return action_data

    

class EncryptedDocument(models.Model):
    _name = 'encrypted.document'
    _description = 'encrypted document'
    
    name = fields.Char('Name')
    blob = fields.Text('Encrypted Blob')
    database_id = fields.Many2one('server.database', ondelete='restrict', string='Database')
