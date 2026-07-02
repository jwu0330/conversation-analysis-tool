"""Bloom 提問序列分析（獨立模組）。

刻意與 src/core 完全解耦：本套件不 import core 的任何東西，
只吃一份 pandas DataFrame，產出序列、Lag-1 轉移表與圖表。
未來要抽出成獨立工具或串接 GSEQ，都不影響前面的描述統計/檢定功能。
"""
