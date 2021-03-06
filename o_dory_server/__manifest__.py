# -*- coding: utf-8 -*-
# Copyright (c) 2021, Emmie He <heemmie@gmail.com>
{
    "name": "O-DORY Server",
    "summary": "O-DORY is a DORY-style end-to-end encrypted file-storing application. This module contains functionalities of an O-DORY server.",
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
        # "data/server_database.xml",
        "data/server_folder.xml",
        "views/server_views.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "o_dory_server/static/src/scss/primary_variables.scss"),
        ],
    },
}
