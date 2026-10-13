# -*- coding: utf-8 -*-
"""entity.place — 向关卡放置任意实体（P1 主线第一件）。

assemble v1（mods/_vendor/assemble.py）实体插入能力的泛化：v1 只会向新建关卡
插入唯一关卡宿主（0x41400001 金样本克隆）；本模块向**任一现有关卡版本**的 f5
容器放置任意 prefab 实体（合成模板库），并按注册律维护 f6 实体注册面。
底座原则（docs 卷实体写作纪律）：以当前版本 .gil 为底座少造多改——只追加 f5
实体条目与 f6 注册叶，其余顶层字段字节原样保留。

调用（docs/30 P1 批次）：
    r = entity.entity_place(aid=20001018, pos=(5.0, 5.0), guid=0x40460001)  # 显式 guid
    r = entity.entity_place(aid=30003006, pos=(0.0, -10.0))                 # guid=None 台账分配
    # r.version = 关卡新版本号；r.value = {guid/aid/entity_count/...}

═══ 注册律（字节考古定案；仲裁规则=金样本字节>卡片断言>枚举名）═══

研究问题：通用实体需要 f5+f6 双注册吗？
方法：本机全部 33 个关卡金样本的 f5 实体 × f6 树叶全量交叉对账（脚本对账，非目测）。

字节证据：
  1. 编辑器保存图（用户逐件摆放）：f5 实体几乎全部有 tab3 叶——
     1073742021: f5=325 / tab3 叶=320（单分支「未分类页签」：315×cat200 + 5×cat100）
     1073742006: f5=75 / 叶=65（残差=系统族 0x40c×9 + 0x410×1，见证据 4）
     1073741975: f5=57 / 叶=43（残差=系统族 10 + 模板预置怪 0x40800001-05；
                 后者在 tab14 cat2200 另面注册；用户摆的怪 0x40800006-2f
                 共 42 只全部 tab3 cat200）
  2. 模板/商城图（非编辑器逐件摆放）：f5 大量实体无叶——
     1073742025: f5=543（0x404×526 / 0x408×6 / 0x40c×9 / 0x410×1 / 0x414×1），
                 tab3 仅 13 叶 → 526 个 0x404 机关中 525 个无叶照样存活
                 → **机关双注册非功能必需**（v2 §302 卡14「实体查 f6 树
                 cat100/200/300」作无条件律读法须限定）
     1073742023: f5=279 / 叶=1（仅关卡宿主——assemble v1 V5 检查的同源样本）
  3. 怪物双注册硬律成立：全档 132 个 0x408 段 f5 实体中 120 个有 tab3 cat200 叶，
     12 个无叶者全是三图的模板预置怪（tab14 cat2200 另面注册，非无注册）
     ——「怪物须双注册，缺一即不生效」+「缺一不渲染」与字节一致。
  4. 叶形态 = {f1:类别, f2:guid} 9B（cat200 = 08 c8 01 10 <guid varint>）。
     系统族不进 tab3：0x40c（镜头族 aid=1086324737）→ tab9 cat1700，
     0x410（出生点/自定义职业）→ tab10 cat1800（26/28 图一致）。
     cat300：33 图 0 例（卡14 的「300」无字节实例——存疑挂账）。
     cat100：6 例且从不单独出现，语义未判不写。
  5. f5 容器内实体排列=摆放序非 guid 序（首实体宿主/镜头可证）→ 新实体尾部追加。

律（本模块执行）：**统一注册**——放置即向 f6 tab3「未分类页签」分支追加叶
{f1:200, f2:guid}。理由：(a) 怪物硬律必须（证据 3）；(b) 机关双注册是编辑器原生
保存形态（证据 1 三图正证），与编辑器往返一致、实体在编辑器实体面板可见可管理；
(c) 多余叶无害有反证（最小注册面 279 实体仅 1 叶的图 + 带宿主叶的关卡经
level.deploy 导入判决 PASS）。

═══ 段位律（guid 分配/校验）═══

  怪物判别 = official_prefab_db type_id==1405（87/87 全怪、0 误报；对照：
  1401=关卡实体×1、1402=机关/造物×2378）；db 无记录时 aid>=30000000 且非
  0x404 形态 → 怪（0x404 形态 aid=复杂造物自指 guid，不算怪）。
  怪 → 0x408 段 [0x40800000,0x40900000)（段错不渲染：合成实证 + 段位表）；
  机关 → 0x404 段 [0x40400000,0x40500000)（合成主用段）。
  1401（关卡实体）拒绝放置：33 图中 30/30 个 1401 全在 0x414 宿主位且每图恰 1 个
  ——关卡宿主归 level.mount 管（S0 唯一宿主前置）。
  guid=None 时台账全档扫描分配（目标图现有 guid + guid_ledger 台账 + 0x414 避让）：
  机关用缺省带 (0x40460001,0x40500000)；怪用 (0x40810000,0x40900000)
  ——低区 0x40800001.. 留给编辑器序贯分配，高区防撞。
  分配即记台账（工具树 guid_ledger.json，产线既有机制）。

异常语义（core.py 三分支）：
  PreconditionError（前置不过，不计失败，换路——全是输入/环境形态问题）：
    工具树未配置（合成模板库在本机研究工具内，开源仓库不附带）/
    关卡无当前版本 / aid 无 prefab 模板 / aid placeable=False / aid=关卡实体(1401) /
    pos/scale/yaw 形态非法 / guid 段位与 aid 类型不符 / guid 与关卡现有内容撞号
    （全档 varint 扫描，含 f5 实体/f6 叶/f10 图）
  ModuleRejected（后验不过，不入账 + 计连续拒绝，4 次 → Voyager 换路信号）：
    产物 roundtrip 失败 / 实体数对账不平 / guid 全档出现位≠2（身份位+注册叶）/
    tab3 注册叶缺失 / trial_gate TRIAL_SICK / 产物不存在

测试分层（mods/selftest）:
  FULL  全链路需工具树（QXY_TOOL_ROOT：合成模板库 + trial_gate）——
        缺工具树整组 SKIP；底座用合成关卡（tests/fixtures，零游戏目录依赖），
        台账 monkeypatch 重定向临时文件，零污染。

状态位：🔶 代码+自测完成（真实导入+试玩 PENDING-GAME——「放进去的实体在
编辑器/游戏里可见可玩」须用户导入终审，通道=level.deploy，本模块只产版本制 .gil）。

遗留：
  L1 真实导入/试玩未测（PENDING-GAME）。
  L2 cat100 语义未判（6 例且从不单独出现）——本模块不写，待字节锚。
  L3 cat300 无字节实例（33 图 0 例）——挂账待锚；本模块按字节证据只写 cat200。
  L4 系统族/模板预置怪注册面（tab9 cat1700 / tab10 cat1800 / tab14 cat2200）
     本模块不触碰——place 只服务用户摆放实体（0x404/0x408 段）。
  L5 多分支 tab3 形态全档未见（33 图全单分支「未分类页签」）——遇多 f3 分支
     关卡时本模块追加到首个 f3 分支，行为待真实样本校准。
  L6 台账写在工具树 guid_ledger.json（产线既有机制）——台账归属状态根未定案。
  L7 俯仰/翻滚旋转（f2.f1/f3 轴）未判——本模块签名只开 yaw。
"""
from __future__ import annotations

from pathlib import Path

from . import core, level
from . import _toolchain

# ---- 既有件（只读依赖，禁改）----
# assemble v1：enc/viv/_fields/_walk_varints/insert_sorted/entity_tab_entry/Container
#   —— level.py 已按文件路径装载 vendored 副本（消除 sys.path 同名歧义），此处复用
assemble = level.assemble
parse, emit = assemble.parse, assemble.emit
# trial_gate 运行器与工具树装载：复用 _toolchain 的收敛入口
_ensure_qxy = _toolchain.ensure_toolchain

# ---- v1 正典常量（assemble v1 同源 + 字节考古增补）----
TREE_TAB_ENTITY = assemble.TREE_TAB_ENTITY      # 3：实体页签
TREE_CAT_ENTITY = assemble.TREE_CAT_ENTITY      # 200：实体注册叶类别（567 叶实证）
BRANCH_NAME_TAB3 = assemble.BRANCH_NAME_TAB3    # 「未分类页签」15B（逐字节证）
BAND_GADGET = (0x40400000, 0x40500000)          # 机关段（合成正典）
BAND_MONSTER = (0x40800000, 0x40900000)         # 怪物段（段错不渲染）
ALLOC_BAND_GADGET = (0x40460001, 0x40500000)    # 台账分配缺省带（避开编辑器低区）
ALLOC_BAND_MONSTER = (0x40810000, 0x40900000)   # 怪分配带（低区留给编辑器序贯分配）
MONSTER_TYPE_ID = 1405                          # official_prefab_db 怪物 type_id（87/87）
TYPE_LEVEL_ENTITY = 1401                        # 关卡实体（唯一宿主，本模块拒绝放置）
AID_MONSTER_MIN = 30000000                      # 怪物 aid 下限（db 无记录时的后备判别）


# ---------------------------------------------------------------------------
# 判别律
# ---------------------------------------------------------------------------

def is_monster_aid(aid: int) -> bool:
    """怪物判别：db type_id==1405（87/87 全怪 0 误报）；无 db 记录时
    aid>=30M 且非 0x404 形态（0x404 形态 aid=复杂造物自指 guid）。"""
    P, _ = _ensure_qxy()
    rec = P.synth.db_lookup(aid)
    if rec is not None:
        return rec.get("type_id") == MONSTER_TYPE_ID
    return aid >= AID_MONSTER_MIN and not (BAND_GADGET[0] <= aid < BAND_GADGET[1])


def required_band(aid: int) -> tuple[int, int]:
    """aid 类型 → guid 必须落的段位（段位律，见模块 docstring）。"""
    return BAND_MONSTER if is_monster_aid(aid) else BAND_GADGET


# ---------------------------------------------------------------------------
# 参数解析（前置：形态问题一律 PreconditionError）
# ---------------------------------------------------------------------------

def parse_pos(pos) -> tuple[float, float, float | None]:
    """pos → (x, z, y|None)。形态：{x,z,y?} / (x,z) / (x,z,y)——y=None=贴地。"""
    try:
        if isinstance(pos, dict):
            x, z = float(pos.get("x", 0.0)), float(pos.get("z", 0.0))
            y = pos.get("y")
            return x, z, (None if y is None else float(y))
        if isinstance(pos, (list, tuple)) and 2 <= len(pos) <= 3:
            x, z = float(pos[0]), float(pos[1])
            return x, z, (float(pos[2]) if len(pos) == 3 else None)
    except (TypeError, ValueError):
        pass
    raise core.PreconditionError(
        f"pos 须为 (x,z)/(x,z,y) 或 {{x,z,y?}}（y=None=贴地），得到: {pos!r}")


def parse_scale(scale) -> tuple[float, float, float] | None:
    """scale → (sx,sy,sz) 正数三元组或 None（=模板缺省 1,1,1）。"""
    if scale is None:
        return None
    try:
        if isinstance(scale, (list, tuple)) and len(scale) == 3:
            v = tuple(float(x) for x in scale)
            if all(x > 0 for x in v):
                return v
    except (TypeError, ValueError):
        pass
    raise core.PreconditionError(f"scale 须为 (sx,sy,sz) 正数三元组，得到: {scale!r}")


# ---------------------------------------------------------------------------
# 字节手术（泛化 assemble v1 的插入模式：f5 尾部追加 + tab3 叶追加）
# ---------------------------------------------------------------------------

def _f5_entity_count(tree) -> int:
    f5s = assemble._fields(tree, 5)
    if not f5s:
        return 0
    return sum(1 for e in parse(f5s[0][2])
               if isinstance(e, list) and e[0] == 1)


def _f5_append(tree, entity_bytes: bytes) -> None:
    """f5 容器尾部追加实体条目 [1,2,字节]（摆放序正典，考古证据 5）；无 f5 则按
    顶层字段升序建（assemble.insert_sorted 同律：全档顶层均升序）。"""
    entry = [1, 2, entity_bytes]
    i5 = next((i for i, x in enumerate(tree)
               if isinstance(x, list) and x[0] == 5), None)
    if i5 is None:
        tree[:] = assemble.insert_sorted(tree, [[5, 2, emit([entry])]])
        return
    ents = parse(tree[i5][2])
    ents.append(entry)
    tree[i5] = [5, 2, emit(ents)]


def _tab3_leaf(tree, guid: int, cat: int = TREE_CAT_ENTITY) -> str:
    """f6 tab3「未分类页签」分支追加叶 {f1:cat, f2:guid}（就地改 tree）。

    返回动作说明。tab3 条目在 → 叶追加到其首个 f3 分支尾部（33 图实证单分支、
    叶按摆放序排列；多 f3 分支形态全档未见）；tab3 条目缺 → 按
    assemble.entity_tab_entry 同构形态创建；f6 容器缺 → 顶层升序建。"""
    leaf = emit([[1, 0, assemble.enc(cat)], [2, 0, assemble.enc(guid)]])
    i6 = next((i for i, x in enumerate(tree)
               if isinstance(x, list) and x[0] == 6), None)
    if i6 is None:
        entry = assemble.entity_tab_entry(guid)   # {f1:tab3, f2:root名, f3:分支(单叶)}
        tree[:] = assemble.insert_sorted(tree, [[6, 2, emit([entry])]])
        return "f6_created_with_tab3_leaf"
    entries = parse(tree[i6][2])
    for k, e in enumerate(entries):
        if not (isinstance(e, list) and e[0] == 1):
            continue
        tr = parse(e[2])
        tab = next((assemble.viv(x[2]) for x in tr
                    if x[0] == 1 and x[1] == 0), None)
        if tab != TREE_TAB_ENTITY:
            continue
        for j, nd in enumerate(tr):
            if not (nd[0] == 3 and nd[1] == 2):
                continue
            branch = parse(nd[2])
            branch.append([5, 2, leaf])           # 叶按摆放序尾部追加
            tr[j] = [3, 2, emit(branch)]
            entries[k] = [1, 2, emit(tr)]
            tree[i6] = [6, 2, emit(entries)]
            return "leaf_appended"
        # tab3 条目在但无 f3 分支（全档未见）→ 建分支再挂叶
        branch = emit([[1, 2, BRANCH_NAME_TAB3], [3, 0, assemble.enc(2)], [5, 2, leaf]])
        tr.append([3, 2, branch])
        entries[k] = [1, 2, emit(tr)]
        tree[i6] = [6, 2, emit(entries)]
        return "branch_created_with_leaf"
    # f6 在但无 tab3 条目 → 追加条目（f6 容器条目序=任意序实证）
    entries.append([1, 2, assemble.entity_tab_entry(guid)[2]])
    tree[i6] = [6, 2, emit(entries)]
    return "tab3_entry_created_with_leaf"


def _guid_occurrences(tree, guid: int) -> tuple[int, list[str]]:
    """全档 varint 扫描 guid 出现位。合法位恰 2：f5 身份位（…f5[…].f1）+
    tab3 注册叶（…f6[…].f2）。其余出现位=悬空引用嫌疑（对账铁律）。"""
    good, stranger = 0, []
    for i, nd in enumerate(tree):
        if not isinstance(nd, list):
            continue
        for path, v in assemble._walk_varints(nd, f"top[{i}]"):
            if v != guid:
                continue
            if ".f5[" in path and path.endswith(".f1"):
                good += 1
            elif ".f6[" in path and path.endswith(".f2"):
                good += 1
            else:
                stranger.append(path)
    return good, stranger


def _scan_used_guids(tree) -> dict[int, list[str]]:
    """当前树全档 varint → {guid: [路径…]}（显式 guid 撞号前置扫描面：
    覆盖 f5 实体号/f6 叶/f10 图号/f15 资产号）。"""
    used: dict[int, list[str]] = {}
    for i, nd in enumerate(tree):
        if not isinstance(nd, list):
            continue
        for path, v in assemble._walk_varints(nd, f"top[{i}]"):
            used.setdefault(v, []).append(path)
    return used


# ---------------------------------------------------------------------------
# 注册模块
# ---------------------------------------------------------------------------

@core.module("entity.place")
def entity_place(aid: int, pos, level_name: str = "hello",
                 guid: int | None = None, yaw: float = 0.0,
                 scale=None) -> core.Result:
    """向关卡当前版本放置一个 prefab 实体，产出新版本 .gil（P1 主线第一件）。

    参数：
        aid         官方 prefab 资产 id（合成模板库；无模板=PRECONDITION）
        pos         位置：{x,z,y?} / (x,z) / (x,z,y)——y=None=贴地（落地规则）
        level_name  版本域名（core 版本制 levels/<名>/v<N>.gil；须已有当前版本）
        guid        实例 id；None → 台账全档扫描分配（段位按 aid 类型，分配即记
                    工具树台账）；显式给定时校验段位律与撞号
        yaw         Y 轴旋转【度】（0=省略旋转消息）
        scale       (sx,sy,sz) 缩放；None=模板缺省

    返回 Result：artifact=装配临时产物（state/tmp 槽，包装器复制成新版本）；
    level=版本域名；value={guid, aid, entity_count, leaf, alloc, band}；
    checks=前置 + roundtrip/实体数对账/全档闭合/注册叶/trial_gate + commit_byte_equal。
    """
    P, _ = _ensure_qxy()

    # ---- 前置①：aid（模板=合成真相，placeable=放置流程①，1401=宿主领地）----
    if not isinstance(aid, int) or isinstance(aid, bool) or aid <= 0:
        raise core.PreconditionError(f"aid 须为正整数，得到: {aid!r}")
    if P.synth.load_template(aid) is None:
        raise core.PreconditionError(
            f"aid {aid} 无 prefab 模板（合成模板库）——先查正确资产 id 再调用")
    rec = P.synth.db_lookup(aid)
    checks = []
    if rec is None:
        checks.append(("aid_db_record", "TRIVIAL: db 无记录（复杂造物族），段位按 aid 形态判"))
    else:
        if rec.get("placeable") is False:
            raise core.PreconditionError(
                f"aid {aid}（{rec.get('name')!r}）placeable=False（official_prefab_db）——"
                "不可放置资产，换 aid")
        if rec.get("type_id") == TYPE_LEVEL_ENTITY:
            raise core.PreconditionError(
                f"aid {aid} 为关卡实体(1401)——唯一宿主归 level.mount 管，本模块不放置")
        checks.append(("aid_placeable", "PASS"))
    checks.append(("aid_has_template", "PASS"))

    # ---- 前置②：参数形态 ----
    x, z, y = parse_pos(pos)
    scale3 = parse_scale(scale)
    yaw = float(yaw)
    monster = is_monster_aid(aid)
    band = required_band(aid)
    checks.append((f"guid_band_{'0x408' if monster else '0x404'}", "PASS"))

    # ---- 前置③：关卡当前版本 ----
    cur_ver = core.current_version(level_name)
    cur = core.read_current(level_name)
    if cur is None:
        raise core.PreconditionError(
            f"关卡 {level_name!r} 无当前版本（levels/ 下无 v<N>.gil）——"
            "先 level.checkpoint/level.mount 建版")
    map_gil = str(core.version_path(level_name, cur_ver))
    c_cur = assemble.Container.load(map_gil)   # 底座容器（取 proto 段+保 file_type 头形制）
    cur_proto = c_cur.proto

    # ---- 前置④：guid（段位律 + 全档撞号扫描 / 台账分配）----
    t_cur = parse(cur_proto)
    if guid is not None:
        if not isinstance(guid, int) or isinstance(guid, bool) or guid <= 0:
            raise core.PreconditionError(f"guid 须为正整数，得到: {guid!r}")
        if not (band[0] <= guid < band[1]):
            raise core.PreconditionError(
                f"guid 0x{guid:x} 不在段 0x{band[0]:x}-0x{band[1]:x} "
                f"（段位律：{'怪物' if monster else '机关'} aid {aid} → "
                f"{'0x408' if monster else '0x404'} 段，段错不渲染/渲染错类）")
        clash = _scan_used_guids(t_cur).get(guid)
        if clash:
            raise core.PreconditionError(
                f"guid 0x{guid:x} 与关卡现有内容撞号（全档 varint 扫描）: {clash[:4]}")
        checks.append(("guid_no_clash", "PASS"))
        alloc = "explicit"
    else:
        alloc_band = ALLOC_BAND_MONSTER if monster else ALLOC_BAND_GADGET
        got = P.alloc_guids(map_gil=map_gil, count=1, band=alloc_band,
                            note=f"entity.place:{level_name}")
        guid = got[0]
        checks.append(("guid_alloc_ledger", "PASS"))
        alloc = f"ledger(0x{alloc_band[0]:x}+)"

    # ---- 执行：合成 → f5 尾部追加 → tab3 注册叶（统一注册律）----
    rot = (None, yaw, None) if yaw else None   # 零值省略正典
    eb = P.entity(aid, x=x, z=z, y=y, scale=scale3, rot=rot, guid=guid)
    n_before = _f5_entity_count(t_cur)
    t_new = parse(cur_proto)
    _f5_append(t_new, eb)
    leaf_action = _tab3_leaf(t_new, guid)

    tmp = core.state_dir() / "tmp" / "entity_place.gil"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    assemble.Container(c_cur.file_type, emit(t_new)).save(str(tmp))

    # ---- 后验（产物读回作证据，坏产物在落版前拦截）----
    c_out = assemble.Container.load(str(tmp))
    if not c_out or not Path(tmp).exists():
        raise core.ModuleRejected("产物不存在或不可读")
    t_out = parse(c_out.proto)
    checks.append(("roundtrip", "PASS" if emit(parse(c_out.proto)) == c_out.proto else "FAIL"))

    n_after = _f5_entity_count(t_out)
    ok_count = n_after == n_before + 1
    checks.append(("entity_count_audit",
                   f"PASS ({n_before}->{n_after})" if ok_count else f"FAIL ({n_before}->{n_after})"))

    good, stranger = _guid_occurrences(t_out, guid)
    ok_closure = good == 2 and not stranger
    checks.append(("closure_guid_occurrences",
                   "PASS 恰2处(身份位+注册叶)" if ok_closure
                   else f"FAIL 合法位{good} 悬空{stranger[:3]}"))

    has_leaf = any(
        v == guid
        for nd in t_out if isinstance(nd, list) and nd[0] == 6
        for path, v in assemble._walk_varints(nd, "f6"))
    checks.append(("tab3_leaf_registered",
                   f"PASS ({leaf_action})" if has_leaf else "FAIL"))

    ok_band = band[0] <= guid < band[1]
    checks.append(("segment_band", f"PASS 0x{guid:x}" if ok_band else f"FAIL 0x{guid:x}"))

    verdict, gate_out = _toolchain.run_trial_gate(str(tmp))
    checks.append(("trial_gate", verdict))
    detail = next((ln.strip() for ln in gate_out.splitlines()
                   if "[SICK]" in ln or "[WARN]" in ln), "")
    if detail:
        checks.append(("gate_detail", detail[:120]))

    bad = [name for name, st in checks if isinstance(st, str) and st.startswith("FAIL")]
    if bad:
        raise core.ModuleRejected(f"后验不过: {bad}")
    if verdict != "TRIAL_PASS":
        sick = " | ".join(ln.strip() for ln in gate_out.splitlines() if "[SICK]" in ln)
        raise core.ModuleRejected(f"trial_gate 拦截: {sick or verdict}")

    # ---- 全过 → 交 core 包装器落版 ----
    return core.Result(
        ok=True, artifact=str(tmp), level=level_name,
        value={"guid": guid, "aid": aid, "entity_count": n_after,
               "leaf": {"tab": TREE_TAB_ENTITY, "cat": TREE_CAT_ENTITY},
               "alloc": alloc, "band": f"0x{band[0]:x}",
               "monster": monster, "pos": {"x": x, "z": z, "y": y},
               "yaw": yaw, "scale": scale3},
        checks=checks)
