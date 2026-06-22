---
title: 测试排版与发布优化
author: 弹壳小能手
image: assets/img/article-top.jpg
summary: 这是一篇用于测试微信排版美化与发布脚本的测试文档。
---

# 微信排版与发布优化测试

这是一段普通的正文文本，用于测试默认的主题排版样式。

## 1. 外部链接转换为脚标测试
我们可以通过以下链接查看更多内容：
- [我的外部链接](https://example.com/guide)
- [另一个外部链接](https://google.com)
- 这是一个微信内部链接（应该不转换）：[微信文章链接](https://mp.weixin.qq.com/s/123456)

## 2. 拼音注音 (Ruby) 语法测试
我们在攻略中需要对一些生僻字或游戏名词进行注音：
游戏名词 [装备]{zhuang bei}，或者是 [弹壳特攻队]{dan ke te gong dui}。

## 3. 图片与布局样式测试

### 3.1 带宽高属性的图片（防止微信拉伸）
<img src="img://等离子剑" width="40" height="40" />

### 3.2 布局样式后缀测试 (如 card, grid2 等)
以下是一个卡片形式的图片：
![等离子剑](img://等离子剑) {type=card}

以下是并排两列的图片 (grid2)：
![等离子剑](img://等离子剑) {type=grid2}
![等离子剑](img://等离子剑) {type=grid2}

以下是并排四列的图片 (grid4)：
![等离子剑](img://等离子剑) {type=grid4}
![等离子剑](img://等离子剑) {type=grid4}
![等离子剑](img://等离子剑) {type=grid4}
![等离子剑](img://等离子剑) {type=grid4}
