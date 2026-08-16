---
title: Attention Is All You Need 文献研读笔记
tags:
  - 深度学习
  - NLP
  - Transformer
  - 论文研读
author: 示例研究员
created: 2026-08-01
---

# Attention Is All You Need 文献研读

## 1. 论文核心贡献
- 摒弃了传统的循环神经网络（RNN）和卷积神经网络（CNN）架构，首次完全依赖自注意力机制（Self-Attention）来建模序列全局依赖关系。
- 提出了 **Transformer** 模型架构，由 Encoder（编码器）和 Decoder（解码器）堆叠而成。
- 关联概念：参考 [[示例_深度学习基础概念]]。

## 2. Multi-Head Attention (多头自注意力机制)
注意力计算公式定义为：
$$Attention(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

- $Q$ (Query), $K$ (Key), $V$ (Value) 分别是输入特征通过不同线性变换投影得到的矩阵；
- 缩放因子 $\sqrt{d_k}$ 用于防止点积结果过大导致 Softmax 梯度饱和。

## 3. 课题组实验结论
- 在学术任务和长文本处理中，Transformer 具备优异的并行训练能力；
- 结合 [[示例_实验室仪器安全管理规范]] 中算力集群使用条例，建议在 GPU 集群上采用 Mixed Precision（混合精度）进行微调。
