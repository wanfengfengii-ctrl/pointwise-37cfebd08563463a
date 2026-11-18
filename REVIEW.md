# 晚班首样复核

早班仍按 README.md 的方式登记批次并固定设备录制。质控员为该清册中的每个曝光报一次人工复核的工时。签发时一次选定复核项。晚班只需查这些项，随后凭成果号和实答领取整批首样。

## 签发口径

沿用原两通道和整批锁存次数的解释规则。每个合格完整顺序按登记清册形成一个首样向量，每个元素是首样事件号或 `None`。完整向量相同的解释合为一个。相同读值的不同事件保留各自身份。

签发的复核项必须让任意两个不同向量至少在一项已选曝光上有不同答复。总工时是选定项的工时和，必须取全局最小。同价时将所选曝光写成升序排列的清册下标序列，取字典序最小者。清册下标从零开始。仅有一个不同向量时签发零成本空计划。所选计划及足以确定全部合法答复的关系，随同一成果和成功回执原子签发。相同证据可以按另一份工时表另行签发。各成果号始终使用各自签发的计划和关系。

## Python 接口

在原 `Station` 上增加以下入口。

| 调用 | 输入与结果 |
| --- | --- |
| `qualification.qualify_release_review(evidence_id, costs, *, after_artifact=None)` | `costs` 是由曝光 ID 到正整数工时的映射。键须恰好覆盖登记清册，映射顺序无关，布尔值非法。返回与原签发入口同型的 `(PublishedArtifact, PublicationReceipt)`。回调沿用原签发时点和回滚语义。 |
| `handoff.pickup_review(artifact_id)` | 返回字典，包含整数 `evidence_id`、清册顺序的 `exposure_ids` 元组和整数 `total_cost`。 |
| `handoff.resolve_review(artifact_id, answers)` | `answers` 是由曝光 ID 到原采样事件号字符串或 `None` 的映射。键须恰好覆盖所选曝光，顺序无关。返回按清册排列的 `(exposure_id, sample)` 元组序列，外层为元组。`sample` 为原 `handoff.source.SourceReading` 或 `None`。取件是只读操作。 |

答复中的 `None` 表示该项已查为空。漏答、多答、非法答复值及不存在于联合关系的答复均报 `ValueError`。零成本空计划接受空映射。取件用固定父证据定位原事件，`SourceReading` 沿用 `evidence_id`、`source_id`、`sample_index`、`event_id`、`tick` 和 `value`。

旧成果通过原目录和 `pickup_report` 读取，在两个新取件入口报 `ValueError` 并说明无计划。未知成果沿用 `UnknownArtifact`。新成果也可走原目录和核定报告入口。工时非法报 `ValueError`，无合法解释沿用 `UnexplainableRecording`，归档提交或回调失败沿用 `PublicationError`。这些失败均不增加成果和成功回执，旧号仍可读取。持久库沿用 README.md 的读写前提。

## 录制样例与核验

`review_examples.py` 提供短录制、交班调用和可重跑的对照。

- A 在第 1 拍关闭，B 同拍开启。采样 r 也在第 1 拍，设备封账为 1。A 和 B 恰有一个取 r。A 的工时为 4、B 为 1 时只查 B。B 答 `None` 得 A=r，B 答 `r` 得 A 为空。两次都指向同一证据的采样下标 0。互换工时另签后只查 A。
- B、C、D 样例的四条采样读值都为 7。两个合法解释仅在 C 的 s、t 间不同，另两个仅在 D 的 t、u 间不同。因此 C、D 必选，两项足以区分全部解释，工时合计 6。C 和 D 各自可空，但同时答空与封账 2 冲突。
- 清册 Z、A、M 中恰有一个曝光得到首样。三项同价时选 Z、A。另一个录制的多条解释都以 `early` 为首样，签发空计划即可领取这条零值读数。

`python3 -B -m review_examples baseline` 核对当前项目中 A、B 都进入原待复检清单。完成新功能后，`python3 -B -m review_examples verify` 执行原回归和新交班对照，`python3 -B -m review_examples demo` 输出签发、关源重开及两种实答的原出处。沿用根目录的 `.pointwise-runtime.json`，其中 `version` 为 1、`kind` 为 `cli`，`setup` 是准备命令的 argv 列表，`verify` 和 `demo` 各是一条 argv 命令。核验失败须返回非零退出码。交付时简述核定、签发与取件之间如何保全所选项和可解答的联合关系。
