"""SeeThrough 补充数据2规则筛选的论文来源阈值。"""

水合评分下限 = -1.5
估算折射率下限 = 1.58
汉森距离_BA上限 = 10.0

规则来源 = {
    "水合评分下限": "Supplementary Fig. 2a：hydration score below -1.5 were excluded from further analysis.",
    "水合能力高于BA": "Supplementary Note 1, p. S21：higher hydration activity than BA.",
    "估算折射率": "Supplementary Note 1, p. S21：eRI > 1.58.",
    "汉森距离": "Supplementary Note 1, p. S21：HSP distance from BA < 10.",
    "人工标签": "Supplementary Note 1, p. S21：no toxic and deleterious effects；Supplementary Data 2未提供逐候选标签。",
    "芳香候选": "Article Fig. 1c / Results：reported aromatic group n = 140；Supplementary Data 2未提供成员ID。",
}
