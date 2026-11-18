# 滨河二号线光电检测交班归档

滨河带材厂二号线检测班用这套归档处理离线光电录制。早班操作员按检测卷登记并接纳原件，质控员核定曝光的首样，晚班接班员在设备关闭后按成果号领取清单。设备分开记录控制和光强读数。同拍的跨通道先后未知，设备还提供独立的整批首样锁存次数。

## 一次交班

1. 早班以卷号和录制来源登记有序曝光清册，获得批次号。相同声明重提复用该号。同键清册冲突或清册内曝光重号时拒绝登记。
2. 操作员将设备录制交给该批次。系统核对设备来源、各通道的拍序、采样事件号、成对控制和终止封账。
3. 合格录制固定后返回证据号。操作员关闭离线端口，归档仍可按号提供原拍、两条通道及设备封账。
4. 质控员提交证据号。核定依次推进各拍，每拍遍历保持各通道原序的交错，沿各条路径保留当前曝光首样。
5. 完整路径的锁存次数与封账一致才参与汇总。结果按清册顺序列出每次曝光的候选、能否空样及处置。
6. 合格批次的成果和成功回执在同一事务签发。无完整解释的批次保留证据供复核；本次成果和回执均不产生。
7. 晚班重开归档，按成果号领取当次固定清单和来源。系统从该成果绑定的证据定位原事件。
8. 接班员沿清册顺序处理待复检条目，同值的候选仍可按原事件号、采样位置和拍号区分。

## 录制与计算口径

`recordings/changeover.json` 和 `recordings/steady.json` 是两份完整样例。录制为 UTF-8 JSON 对象，成员为 `source_id`、`control`、`samples` 和 `seal`。`source_id` 是非空来源号。两个数组保存各通道原序，各自的数组下标从零开始。封账在独立的终止字段中提供，格式为 `{"kind":"seal","latch_count":2}`。缺封账、重复 JSON 成员和非整数封账次数会拒绝接纳。

控制记录含整数 `tick`、`kind`（`open` 或 `close`）及非空 `exposure_id`，可附非空原 `event_id`。每个清册曝光有且仅有一对控制，控制原序中的曝光互不重叠。清册的展示顺序可以与控制发生顺序不同。采样记录含整数 `tick`、通道内唯一的非空 `event_id` 和整数 `value`。两条记录可以具有相同读值。每个通道的拍号非递减，早拍先于晚拍，两个通道在同拍可按多种方式交错。

曝光只锁存开启期间第一条采样。曝光外的读数与曝光内后续读数也保存在证据中。零光强是实际设备整数计数。空样指某条合格完整顺序下该曝光没有首样。候选按采样位置排序，只有唯一候选且没有空样见证时处置为 `confirmed`，其余为 `review`。读值及拍号按整数编解码。首样出处由证据号、采样位置和原事件号共同定位。

换接样例中，第一拍的 `r` 和 `s` 以及第二拍的 `t` 处在 A、B 换接附近。设备声明两次锁存，因此 `r` 必须在 A 关闭前被锁存。`s` 在 B 开启前抵达时，B 可取 `t`；在 B 开启后抵达时，B 可取 `s`。因此 A 确认 `r`，B 保留 `s`、`t` 并待复检，两个曝光均不可空。稳定样例中两次读数都为 7，曝光 C 确认事件 `early-c`。

## Python 接口

使用 Python 3.11 标准库。`Station(path)` 把登记、接纳、核定、目录和取件接到同一个 SQLite 文件。`initialize()` 可重复执行，保留已登记、已固定、已签发的内容，并且不改写外部录制。

```python
from capture.port import OfflineRecordingPort
from station import Station

station = Station("shift.sqlite3")
station.initialize()
batch_id = station.registry.register("coil-071", "line-2/optical-07", ("A", "B"))
with OfflineRecordingPort("recordings/changeover.json") as port:
    evidence_id = station.capture.ingest(batch_id, port)
artifact, receipt = station.qualification.qualify_release(evidence_id)

later = Station("shift.sqlite3")
later.initialize()
report = later.handoff.pickup_report(receipt.artifact_id)
```

| 接口 | 返回值与失败语义 |
| --- | --- |
| `registry.register(roll_id, source_id, exposure_ids)` | 返回批次号。非法清册报 `ValueError`，冲突报 `RegistrationConflict`。 |
| `capture.ingest(batch_id, port)` | 返回证据号。未知批次报 `UnknownBatch`，结构错误或来源错绑报 `ValueError` 的对应子类。文件 I/O 错误由端口传出。 |
| `evidence.get(evidence_id)` | 返回不可变的 `FixedEvidence`。未知证据报 `UnknownEvidence`。 |
| `qualification.qualify_release(evidence_id)` | 返回 `PublishedArtifact` 和 `PublicationReceipt`。无完整解释报 `UnexplainableRecording`，发布事务失败报 `PublicationError`。 |
| `catalog.get(artifact_id)`、`catalog.get_receipt(artifact_id)` | 精确读取已签发成果和回执。缺记录分别报 `UnknownArtifact`、`UnknownReceipt`。 |
| `handoff.pickup_report(artifact_id)` | 返回 `PickupReport`。未知成果报 `UnknownArtifact`。报告含完整曝光清单和待复检条目。 |

`RecordingPort` 提供 `read()` 和 `close()`。调用方负责关闭端口。`EvidenceArchive.store` 接收已按对应批次验证的结构化通道和封账，`CaptureService.ingest` 是外部录制的校验入口。发布接口可接收 `after_artifact` 回调，回调在 SQLite 插入成果之后、插入回执之前调用。回调抛错时发布回滚，旧成果仍按原号可读。持久库以已验证录制和应用接口写入为前提。

## 命令与回归

在项目根目录执行。

```sh
python3 -B -m unittest discover -s tests -t . -v
python3 -B -m station demo
```

演示用临时归档签发两卷，关闭端口后重开归档，按第一份成果号打印完整清单、待复检条目和原样出处。每个回归用独立的临时归档，覆盖登记和接纳拒绝、同拍换接、零值与同值异事件、无解拒发、事务回滚和按固定号取件。

日常命令也可分开执行。下面的编号适用于新归档，复用归档时使用上一步实际返回的编号。

```sh
python3 -B -m station --archive shift.sqlite3 register coil-071 line-2/optical-07 A B
python3 -B -m station --archive shift.sqlite3 ingest 1 recordings/changeover.json
python3 -B -m station --archive shift.sqlite3 qualify 1
python3 -B -m station --archive shift.sqlite3 pickup 1
```
