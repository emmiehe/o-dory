# -*- coding: utf-8 -*-
# Copyright (c) 2021, Emmie He <heemmie@gmail.com>
{
    "name": "ODORY",
    "summary": "ODORY is a DORY-style end-to-end encrypted file-storing application.",
    "license": "LGPL-3",
    "description": """
Reproducing Keyword Search and Document Retrieval in Encrypted File-storing Systems.
    """,
    "author": "Emmie He",
    "website": "",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/server_database_views.xml",
        "wizard/odory_client_wizard_views.xml",
        "views/odory_client_views.xml",
    ],
}
