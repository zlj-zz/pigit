# -*- coding: utf-8 -*-
"""
Module: tests/app/test_body_host.py
Description: BodyHost show_detail/show_product must not deactivate children.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from pigit.app_body_host import BodyHost
from pigit.termui import Component


class _Box(Component):
    def __init__(self, id: str) -> None:
        super().__init__(id=id)
        self.deactivated = 0

    def deactivate(self) -> None:
        self.deactivated += 1
        super().deactivate()


def test_show_detail_does_not_deactivate_product():
    product = _Box("product")
    detail = _Box("detail")
    host = BodyHost(product, detail, id="body")
    host.show_detail()
    assert host.is_detail_open is True
    assert product.deactivated == 0
    assert detail.deactivated == 0


def test_show_product_does_not_deactivate_detail():
    product = _Box("product")
    detail = _Box("detail")
    host = BodyHost(product, detail, id="body")
    host.show_detail()
    host.show_product()
    assert host.is_detail_open is False
    assert detail.deactivated == 0
    assert product.deactivated == 0
