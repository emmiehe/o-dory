# -*- coding: utf-8 -*-
# Copyright (c) 2021, Emmie He <heemmie@gmail.com>
{
    "name": "O-DORY Client",
    "summary": "O-DORY is a DORY-style end-to-end encrypted file-storing application. This module contains functionalities of an O-DORY client.",
    "license": "LGPL-3",
    "description": """
Reproducing Keyword Search and Document Retrieval in Encrypted File-storing Systems.
    """,
    "author": "Emmie He",
    "website": "",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": ["web"],
    "data": [
        "views/templates.xml",
        "security/ir.model.access.csv",
        "data/o_dory_account.xml",
        "wizard/client_wizard_views.xml",
        "views/client_views.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "o_dory_client/static/src/scss/primary_variables.scss"),
        ],
    },
}
