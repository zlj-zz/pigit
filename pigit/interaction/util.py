# -*- coding:utf-8 -*-


class TermSize(object):
    width: int = 0
    height: int = 0

    @classmethod
    def set(cls, width, height):
        cls.width = width
        cls.height = height
