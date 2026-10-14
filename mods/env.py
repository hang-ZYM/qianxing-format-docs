# -*- coding: utf-8 -*-
"""env.set — 关卡环境（夜晚/白天/纯色）设置模块（案例 #76）。

输出路径（2026-10-14 #76 字节定案）：
  关卡环境 = **f15 资产库**里一条 `{f1: guid, f2: 类型码 26, f4: 组件1(命名), f4: 组件70(数据)}`，
  数据在 **`f75`**（`f75 → f1 → 参数块`）；并须在 **f6 资源树** category **56**
  (=`AssetType.Environment`) 下以节点 `f5 = {f1: 5400 (=ResourceCategory.Environment), f2: guid}`
  注册。出厂默认槽 = guid **0x46C00001** / 名 "环境配置"，每张真实图都有（从零合成的 .gil
  若缺整个 f15，则用编辑器内置默认 = 白天）。

参数档位来自官方展示图 `1073741954.gil` 的**具名预设**（逐字节移植，不自造值）：
  0x46c00002 '白天' / 0x46c00003 '夜晚' / 0x46c00005 '黑色' / 0x46c00006 '白色'。

另一条能力 **`env.direct_environment`（字段直写，不整包移植）**——2026-10-14 新采：
  取真实样本预设作**底座**，只覆写 f75.f1.f1 里**已解码语义**的字段，其余字节不动：
    f24.f2 = 太阳亮度(f32)   f25.f2 = 月亮亮度(f32)   f26.f2 = 受光颜色(uint32 ARGB)
    f30-33.f2 = 天空背景色(上/下层 × 向阳/背阳)      f34-37.f2 = 环境颜色(顶/侧/地面/光晕)
    f47.f2 = 云/远景色调(★旧命名「雾色」——见下)     f16 = 夜标记
  依据：`黑色` 预设与 `白天` **关键帧逐字段相同**、仅把 f26/f30-37/f47 的 f2 置 0 即全黑
  → 证明「静态渲染读 f2，f3 关键帧属'随时间自动切换'数据」（故直写只动 f2，关键帧保真实样本）。

【2026-10-14 追加 · 案例 #77「雾」与「生效目标」】
  用户实测改件（地图 1073742035/2036，编辑器保存）对我方 v17 逐字段对拍后定案：
  * **真「雾」= 天气配置**，落在 **`f75.f1.f3`**（不是 f47）。依据：
    ① 官方语料：「3.天气 … 天气类型：当前仅支持配置雾；
       距离雾设置 / 高度雾设置」——环境配置下挂天气，天气类型只有雾。
    ② 字节：有雾的图（1073741954 剧情回顾-蒙德 / 1073742033 黑 / 1073742036）在
       `f75.f1.f3` 有 500~613B 载荷 `{f1:1, f2:{f1:1,f2:'天气1',f3:1,f51:天气参数群}, f501:1}`；
       无雾的图（我方 v17 与全部预设）`f75.f1.f3 = {f501:1}`（3B 占位）。
    → 开关 = `f75.f1.f3` 的 {f1,f2} 有无。雾参数值 **移植自用户件**（见 WEATHER_FOG_HEX 注释）。
  * 「生效目标 / 参考时间点」= `f75.f1.f1` 的 **repeated f1**（我方 v17 为空；用户件补了 8 条
    `{f1:enum=0, f2:uint 1..7}` + 1 条全空）。用户语「你的环境没有绑定角色，我绑定了」指此。
    f1 元素类（反编译）= `gAqlPYvXySiCOGumHioL { f1: enum O64cM60CDshW0fYqf34D(成员已剥), f2: uint }`。

  ★ 命名更正：旧版把 f47 记作「雾色」。f47 **不是**雾（雾在 f75.f1.f3）。f47 参数名保留兼容，
    但其语义应读作「云/远景类颜色」，未定案 —— 见 本项目内部报告。

四要素
  前置（PreconditionError：换路，不计拒绝）
    P1 preset ∈ {very_dark, extreme_dark, day, white}（映射真实样本具名预设；别名词见下）
    P2 关卡有当前版本（version>0）
    P3 真实样本图 1073741954.gil 在位、且含目标预设
    P4 底座能 roundtrip（保序保编码前提）
  执行：合成 f15 + 追 f6 cat56 → state/tmp 槽（版本域外）
  后验（ModuleRejected：不入账，指针不动）
    V1 roundtrip      输出可解析且字节守恒
    V2 变更面收口      仅 f6 变 + f15 新增；其余顶层字段逐字节不变
    V3 f6 旧条目守恒    追加前既有 f6 条目逐字节保留
    V4 读回定性        guid=0x46C00001 / 类型码=26 / 名="环境配置"
    V5 载荷保真        comp70 载荷逐字节 == 真实样本预设载荷

调用：
    env.set_environment(level_name="m4", preset="very_dark")
    ok → version=新版本号；value=新版本 .gil 路径；artifact=state/tmp 槽产物

遗留：
    L1 档位仅源真实样本具名 4 种；其余（如"夜晚天气"）未采。
    L2 **生效机制未在编辑器实测**（单配置图无独立 active 指针，全档归纳为"f15 有即生效"）；
       若导入不变暗，用户键一键兜底（见 本项目内部报告），据其图补此模块。
    L3 不变量6 风险：真实样本 1073741954 为较早官方图，载荷字段集与出厂结构略异（含 f1×8/f16/f19、
       缺 f3）——本模块**整包移植**该预设，不做逐字段合成。
    L4 若底座已有环境配置（f15 已达），本模块会**新增第二条**（同 guid 0x46C00001）——
       多配置图由节点图切换，语义未判；当前 M4 无 f15，不触发。
"""
from __future__ import annotations

import struct

from . import config, core  # core 自举把 qxfmt 路径加入 sys.path

from qxfmt.container import Container                      # noqa: E402
from qxfmt.pbtree import parse, first, varint_value, emit, roundtrip, set_body  # noqa: E402

SRC_MAP = "1073741954"             # 官方展示图（具名环境预设；用户自备于本机游戏目录）
ENV_GUID = 1186988033              # 0x46C00001 出厂默认环境槽
ENV_NAME = "环境配置"
ENV_TC = 26
RES_CAT_ENV = 5400                 # ResourceCategory.Environment
ASSET_TYPE_ENV = 56                # AssetType.Environment（f6 category）

# preset 名 → (真实样本 guid, 中文预设名)
_PRESETS = {
    "very_dark":    (0x46c00003, "夜晚"),
    "extreme_dark": (0x46c00005, "黑色"),
    "day":          (0x46c00002, "白天"),
    "white":        (0x46c00006, "白色"),
}


def _gi(nodes, f):
    x = first(nodes, f)
    return varint_value(x) if (x and x[1] == 0) else None


def _ev(n):
    out = b''
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _src_map_path():
    """真实样本图 1073741954.gil 的路径（游戏目录 savelevel；目录式与平铺两形态都认）。

    位置经 mods/config 解析（QXY_GAME_SAVELEVEL / 默认探测）；未配置或文件不在位
    返回 None——调用方据此如实抛 PreconditionError（换路，不计失败），绝不猜路径。
    """
    sl = config.game_dir("savelevel")
    if sl is None:
        return None
    for p in (sl / SRC_MAP / f"{SRC_MAP}.gil", sl / f"{SRC_MAP}.gil"):
        if p.is_file():
            return str(p)
    return None


def _extract_env_entry(preset_guid):
    c = Container.load(_src_map_path())
    top = parse(c.proto, strict=False)
    f15 = first(top, 15)
    if f15 is None:
        return None
    for ent in parse(f15[2], strict=False):
        if ent[0] != 1:
            continue
        e = parse(ent[2], strict=False)
        if _gi(e, 1) == preset_guid and _gi(e, 2) == ENV_TC:
            return parse(ent[2], strict=False)
    return None


def _env_payload(entry_nodes):
    for f, wt, body in entry_nodes:
        if f == 4 and wt == 2:
            cn = parse(body, strict=False)
            if _gi(cn, 1) == 70:
                for cf, cwt, cb in cn:
                    if cf in (75, 80):
                        return cb
    return None


def _rewrite_entry(entry_nodes):
    """entry guid → 0x46C00001；组件1 名 → '环境配置'。"""
    out = []
    for f, wt, body in entry_nodes:
        if f == 1 and wt == 0:
            out.append([1, 0, _ev(ENV_GUID)])
        elif f == 4 and wt == 2:
            cn = parse(body, strict=False)
            if _gi(cn, 1) == 1:
                new = []
                for cf, cwt, cb in cn:
                    if cf == 11 and cwt == 2:
                        new.append([11, 2, emit([[1, 2, ENV_NAME.encode('utf-8')]])])
                    else:
                        new.append([cf, cwt, cb])
                out.append([4, 2, emit(new)])
            else:
                out.append([f, wt, body])
        else:
            out.append([f, wt, body])
    return out


# ---- 字段直写（env.direct）：只改 f75.f1.f1 里已解码语义字段（f2 静态值）----

F_SUN = 24        # 太阳，f2 = 亮度(f32)
F_MOON = 25       # 月亮，f2 = 亮度(f32)
F_LIGHT = 26      # 受光/主光颜色 ARGB(uint32)
F_SKY = (30, 31, 32, 33)      # 天空背景色：上层向阳/上层背阳/下层向阳/下层背阳
F_AMBIENT = (34, 35, 36, 37)  # 环境颜色：顶/侧/地面 + 光晕
F_FOG = 47        # ★旧命名「雾色」；实证非雾（真雾见 F_WEATHER）。语义未定案，保留兼容
F_NIGHT = 16      # 夜标记（有月亮/星等）

# ---- 案例 #77：雾（天气配置）与生效目标（f75.f1 层） ----
F_TARGETS = 1     # f75.f1.f1 内 repeated 生效目标/参考时间点 {f1:enum, f2:uint}
F_WEATHER = 3     # f75.f1.f3 天气配置（天气类型当前仅支持"雾"）

# 「无雾」占位 = 全部预设的默认形态（仅 f501=1）
WEATHER_OFF_HEX = "a81f01"

# ★ 移植（非自造）：以下两段字节逐字节取自**用户编辑器保存的图**
#   （本机游戏目录 savelevel 下 1073742036/1073742036.gil，2026-10-14 保存），
#   f15 条目 guid=0x46c00001 / tc=26 (环境配置)：
#     WEATHER_FOG_HEX  ← f75.f1.f3 （天气配置=雾，613B）
#     TARGETS_HEX      ← f75.f1.f1 的 8 条 repeated f1（30B）
#   依据：不变量「禁克隆产出物」在雾域**无法适用**——雾参数字段语义未逐项解出（距离雾/高度雾
#   子项未对号），故按任务纪律「禁猜：宁可只支持照抄用户那组值」整段移植，不做逐字段合成。
WEATHER_FOG_HEX = (
    "080112dd0408011207e5a4a9e6b0943118019a03cc04100140016d0000a0407a74080110aaa98efc0f1a0c08e784f1f80f12040804101e"
    "1a0c08fdbcd5f90f12040805103b1a0a08a6ff91f90f120208071a0c0893f3fdfa0f12040807103b1a0a0896f785fb0f120208101a0c08"
    "c9fcfdfe0f12040811101e1a0c08d5cccdfc0f12040812101a1a0c08e784f1f80f12040812102c820176080110aaa98efc0f1a0c08c1a39e"
    "fb0f12040804101e1a0c08e6f5eefb0f12040805103b1a0a08ff8df7fc0f120208071a0c08ff8df7fc0f12040807103b1a0c08ff8df7fc0f12"
    "04080d101e1a0c08ff8df7fc0f1204081010011a0c08ff8df7fc0f12040811101f1a0c08c1a39efb0f1204081310048a012615000016451a"
    "070d0000164512001a090d000048431202080a1a0b0d0000164512040817103b92012615398e633f1a070d398e633f12001a090d0000803f12"
    "02080a1a0b0d398e633f12040817103b9a01171a0212001a090d0000803f1202080a1a0612040817103ba20174080110aaa98efc0f1a0a0881"
    "b781f80f120208041a0a08ffefbafb0f120208071a0c08ff89fffb0f12040807103b1a0c08ff89fffb0f1204080d101e1a0c08fde1bafa0f12"
    "04080f102e1a0c08db8efeff0f12040811100a1a0c08f8badeff0f1204081210101a0c0881b781f80f120408131002aa01211a070da69b443b12"
    "001a090d0000a0401202080a1a0b0da69b443b12040817103bb2011b15000020411a070d0000204112001a0b0d0000204112040817103bba01"
    "2615000048421a070d0000484212001a090d12f9fc421202080a1a0b0d0000484212040817103bc20100c80101a81f01"
)
TARGETS_HEX = "0a000a0210010a0210020a0210030a0210040a0210050a0210060a021007"


def _fog_block(fog_color=None, fog_far_dist=None, fog_set=None,
               fog_block_hex=None) -> bytes:
    """生成 f3 天气配置字节。

    fog_block_hex = 整段移植（用给定 f51 块替换底座块，见「高度雾」件）；
                    给了它则忽略 fog_color/fog_far_dist/fog_set（但仍在移植块上按需改色）。
    fog_set       = {字段号: 值} —— 逐字段直写（单变量对照件用）；数值字段 f13(标量) 与
                    f17/f18/f21/f22/f23(组) 均支持；组无 base 时会补 base（块长可能变）。
    """
    if fog_block_hex is not None:
        b = bytes.fromhex(fog_block_hex)
        t = parse(b, strict=False)
        if first(t, 2) is None or first(parse(first(t, 2)[2], strict=False), 51) is None:
            raise ValueError("fog_block_hex 非合法雾块（缺 f2 天气条目 / f51）")
        if fog_color is not None:
            b = _set_fog_color(b, fog_color)
        return b
    b = bytes.fromhex(WEATHER_FOG_HEX)
    if len(b) != 613:
        raise ValueError(f"雾块长度异常：{len(b)} != 613")
    if not bytes.fromhex(WEATHER_OFF_HEX) == b'\xa8\x1f\x01':
        raise ValueError("占位常量异常")
    if fog_color is not None:
        b = _set_fog_color(b, fog_color)
    if fog_far_dist is not None:
        b = _set_fog_scalar(b, FOG_FAR_DIST, float(fog_far_dist))
    if fog_set:
        for field, value in fog_set.items():
            b = _set_fog_field(b, int(field), float(value))
    return b


# 雾「远雾点距离(m)」= f51.f17（base + 全部关键帧）。证据：林夕镇同图 5 预设
#   夜空(望远)=3000 / 跳楼区大雾=200 / 噩梦区=200 / 夕阳=1200；阿刻洛斯=200。
#   → 越小 = 雾越近 = 看得越短（视野限制器）。【强实证关联，仍属推断语义】
FOG_FAR_DIST = 17


def _set_fog_scalar(block: bytes, field: int, value: float) -> bytes:
    """把雾块 f51 某 float 组（如 f17）的 base f2 与其全部关键帧 f3.f1 设为 value。

    只动这一个字段（base + 该字段自身的关键帧）；其余字节保持。f32 定长 → 块长不变。
    """
    t = parse(block, strict=False)
    m_node = first(t, 2)
    m = parse(m_node[2], strict=False)
    f51_node = first(m, 51)
    s51 = parse(f51_node[2], strict=False)
    nd = first(s51, field)
    if nd is None or nd[1] != 2:
        raise ValueError(f"雾块缺 float 组 f{field}")
    grp = parse(nd[2], strict=False)
    enc = _f32(value)
    for i, node in enumerate(grp):
        if node[0] == 2:                      # base
            if node[1] != 5:
                raise ValueError(f"f{field} base f2 非 f32")
            grp[i] = [2, 5, enc]
        elif node[0] == 3:                    # 关键帧 {f1:值, f2:时间}
            kf = parse(node[2], strict=False)
            for j, kn in enumerate(kf):
                if kn[0] == 1:
                    if kn[1] != 5:
                        raise ValueError(f"f{field} 关键帧 f1 非 f32")
                    kf[j] = [1, 5, enc]
            grp[i] = [3, 2, emit(kf)]
    nd[2] = emit(grp)
    f51_node[2] = emit(s51)
    m_node[2] = emit(m)
    return emit(t)


# 雾块 f51 里三个「颜色」字段（ARGB uint32 组，base 值 = 静态渲染读的雾色）
FOG_COLOR_FIELDS = (15, 16, 20)


def _set_fog_color(block: bytes, argb: int) -> bytes:
    """把雾块 f51 的 f15/f16/f20 三个颜色组的 base f2 改成 argb（其余字节保持）。

    只动这 3 个 base 值（= 「雾色」，见 本项目内部报告）；关键帧（f3）不动。
    要求 argb 的 varint 编码与 0xFF8394AA 同长（5B，即 α=0xFF 时恒成立），
    否则整块长度会变（仍合法，但 diff 会整体位移）。
    """
    t = parse(block, strict=False)
    m_node = first(t, 2)
    m = parse(m_node[2], strict=False)
    f51_node = first(m, 51)
    s51 = parse(f51_node[2], strict=False)
    enc = _ev(argb & 0xFFFFFFFF)
    for f in FOG_COLOR_FIELDS:
        nd = first(s51, f)
        if nd is None or nd[1] != 2:
            raise ValueError(f"雾块缺颜色字段 f{f}")
        grp = parse(nd[2], strict=False)
        hit = False
        for i, node in enumerate(grp):
            if node[0] == 2:
                if node[1] != 0:
                    raise ValueError(f"f{f} 颜色组 base f2 非 uint")
                grp[i] = [2, 0, enc]
                hit = True
                break
        if not hit:
            raise ValueError(f"f{f} 颜色组缺 base f2(uint)")
        nd[2] = emit(grp)
    f51_node[2] = emit(s51)
    m_node[2] = emit(m)
    return emit(t)


def _set_fog_field(block: bytes, field: int, value: float) -> bytes:
    """通用：把雾块 f51 的某数值字段设为 value。

    支持两类：
      * 标量 f32（如 f13，wiretype 5）——直接改值；
      * f32 组（如 f17/f18/f21/f22/f23，wiretype 2）——改 base（f2）与其全部关键帧（f3.f1）；
        组无 base 时在组首补一个 base（**块长可能增加**，见案例 #81）。
    字段不存在时按字段序插入一个新组 {f2: base}（**块长增加**）。
    """
    t = parse(block, strict=False)
    m_node = first(t, 2)
    m = parse(m_node[2], strict=False)
    f51_node = first(m, 51)
    s51 = parse(f51_node[2], strict=False)
    enc = _f32(value)
    nd = first(s51, field)
    if nd is None:                                   # 不存在 → 插入新组
        grp = [[2, 5, enc]]
        pos = len(s51)
        for i, x in enumerate(s51):
            if x[0] > field:
                pos = i
                break
        s51.insert(pos, [field, 2, emit(grp)])
    elif nd[1] == 5:                                 # 标量 f32
        nd[2] = enc
    elif nd[1] == 2:                                 # f32 组
        grp = parse(nd[2], strict=False)
        hit = False
        for i, node in enumerate(grp):
            if node[0] == 2:
                if node[1] != 5:
                    raise ValueError(f"f{field} base f2 非 f32（wt{node[1]}），拒绝改写")
                grp[i] = [2, 5, enc]
                hit = True
                break
        if not hit:                                  # 无 base → 组首补 base（块长变）
            grp.insert(0, [2, 5, enc])
        for i, node in enumerate(grp):
            if node[0] == 3:                          # 关键帧 {f1:值, f2:时间}
                kf = parse(node[2], strict=False)
                for j, kn in enumerate(kf):
                    if kn[0] == 1:
                        if kn[1] != 5:
                            raise ValueError(f"f{field} 关键帧 f1 非 f32")
                        kf[j] = [1, 5, enc]
                grp[i] = [3, 2, emit(kf)]
        nd[2] = emit(grp)
    else:
        raise ValueError(f"f{field} 线型 wt{nd[1]} 不支持直写")
    f51_node[2] = emit(s51)
    m_node[2] = emit(m)
    return emit(t)


def _payload_fog_color(payload: bytes, argb: int) -> bytes:
    """在**整段移植的 f75 载荷**上只改雾色（f15/f16/f20 base），其余字节不动。

    用于「以用户手调载荷为底座、只换雾色」的对照件（案例 #81）。
    """
    t = parse(payload, strict=False)
    a_node = first(t, 1)
    a = parse(a_node[2], strict=False)
    w = first(a, F_WEATHER)
    if w is None or w[1] != 2:
        raise ValueError("载荷内无雾块（f75.f1.f3），拒绝改色")
    w[2] = _set_fog_color(w[2], argb)
    set_body(a_node, a)
    return emit(t)


def _targets_nodes():
    """移植块 → 8 个 f1 节点列表（解析一次作模板）。"""
    nodes = parse(bytes.fromhex(TARGETS_HEX), strict=False)
    if len(nodes) != 8 or any(n[0] != 1 for n in nodes):
        raise ValueError("生效目标块形态异常（应 8 条 f1）")
    return nodes


def _f32(x):
    return struct.pack('<f', float(x))


def _set_f2(msg_nodes, body, wt):
    """在消息子节点里设/插入 f2（保持字段序，f2 恒排在最前）。"""
    for nd in msg_nodes:
        if nd[0] == 2:
            if nd[1] != wt:
                raise ValueError(f"f2 线型不一致：现有 wt{nd[1]} vs 期望 wt{wt}")
            nd[2] = body
            return
    pos = 0
    for i, nd in enumerate(msg_nodes):
        if nd[0] > 2:
            pos = i
            break
    msg_nodes.insert(pos, [2, wt, body])


def _ensure_flag(cfg, field, present):
    """确保 cfg 有/无一个 varint 标记字段（保持字段序）。"""
    nd = first(cfg, field)
    if present and nd is None:
        pos = len(cfg)
        for i, x in enumerate(cfg):
            if x[0] > field:
                pos = i
                break
        cfg.insert(pos, [field, 0, _ev(1)])
    elif not present and nd is not None:
        cfg.remove(nd)


def _cfg_of(payload):
    """f75 payload → 设置群 f75.f1.f1 的子节点列表。"""
    t = parse(payload, strict=False)
    a = parse(first(t, 1)[2], strict=False)
    return parse(first(a, 1)[2], strict=False)


def _set_targets(cfg, present: bool):
    """确保 f75.f1.f1(cfg) 有/无 生效目标/参考时间点 的 repeated f1 块（保持字段序：f1 最前）。"""
    have = [n for n in cfg if n[0] == F_TARGETS]
    if present:
        if have:
            return
        blk = _targets_nodes()
        for i, nd in enumerate(blk):
            cfg.insert(i, [nd[0], nd[1], nd[2]])
    else:
        for nd in have:
            cfg.remove(nd)


def _set_weather(a, on: bool, fog_color=None, fog_far_dist=None,
                 fog_set=None, fog_block_hex=None):
    """确保 f75.f1 的天气配置 f3 有/无雾块（保持字段序）；on 时可选改雾色/远雾点距离/逐字段/整段移植。"""
    nd = first(a, F_WEATHER)
    body = (_fog_block(fog_color, fog_far_dist, fog_set, fog_block_hex)
            if on else bytes.fromhex(WEATHER_OFF_HEX))
    if nd is not None:
        if nd[1] != 2:
            raise ValueError("f3 线型非 bytes，拒绝改写")
        nd[2] = body
        return
    pos = len(a)
    for i, x in enumerate(a):
        if x[0] > F_WEATHER:
            pos = i
            break
    a.insert(pos, [F_WEATHER, 2, body])


# ---- 案例 #83：时间推进（「随时间自动切换」+ 参数组时点表） ----
# 字节输出路径（对照用户 2038 存档 guid 0x46C00002、名「时间」的环境，f75=1005B；其分析见
# 本项目内部报告 §6）：
#   * cfg 顶层 `f3=1`        = 「随时间自动切换」总开关（缺 = 关）
#   * 参数组内多出的 `f1=1`  = 该参数「时间曲线生效」位（缺 = 该参数走静态 base f2）
#   * 参数组 `f2`            = 静态基准值（无时点表时渲染读它，案例 #76 已证）
#   * 参数组 `f3`(repeated)  = 时点表关键帧 `{f1:值, f2:{f1:小时, f2:分钟}}`
#     —— 分钟=0 时**省略** f2（官方规范形；2038「时间」组 f30 = `…0810…` 见 `12020813`）
#   * 无环境级「流速」字段 → 推进速度仍由关卡级 f11.f1.f18 决定（§6.4/§6.5）
F_TIME_SWITCH = 3    # cfg 顶层 f3：随时间自动切换
G_TIME_FLAG = 1      # 参数组内 f1：时间曲线生效位

# 「关卡设置」f11.f1（基础页签·时间设置）：f17=初始时间点(varint,0–24) f18=每秒流逝分钟(f32)
LEVEL_F = 11
LEVEL_TIME_INIT = 17
LEVEL_TIME_SPEED = 18


def _level_f11f1(t17=None, t18=None) -> bytes:
    """构造 f11.f1（关卡设置·基础页签）字节：默认字段 + 初始时间点 f17 + 每秒流逝分钟 f18。

    默认字段值逐字段核自用户存档 `1073742033`（f1=生效范围 500³；f6..f26 开关常数；
    f14=1.2 f15=2 f20=30）。t18=None ⇒ **不写 f18**（字节面等于 0——「反编译只在值≠0 时写」）。
    """
    nodes = [
        [1, 2, emit([[1, 5, _f32(500.0)], [2, 5, _f32(500.0)], [3, 5, _f32(500.0)]])],
        [2, 2, b''],
        [6, 0, _ev(1)], [7, 0, _ev(8)], [8, 0, _ev(1)], [9, 0, _ev(8)],
        [10, 0, _ev(1)], [12, 0, _ev(1)], [14, 5, _f32(1.2)], [15, 0, _ev(2)],
    ]
    if t17 is not None:
        nodes.append([LEVEL_TIME_INIT, 0, _ev(int(t17))])
    if t18 is not None:
        nodes.append([LEVEL_TIME_SPEED, 5, _f32(float(t18))])
    nodes += [[20, 0, _ev(30)], [26, 0, _ev(1)]]
    return emit(nodes)


def _set_time_switch(cfg, on: bool = True):
    """cfg 顶层 f3=1/缺（「随时间自动切换」总开关），保持字段序。"""
    _ensure_flag(cfg, F_TIME_SWITCH, on)


def _group_of(cfg, field):
    nd = first(cfg, field)
    if nd is None or nd[1] != 2:
        raise ValueError(f"cfg 缺参数组 f{field}（无法写时点表）")
    return nd


def _kf_node(value, hour, minute, wt):
    """一个时点表关键帧：`{f1:值, f2:{f1:小时, f2:分钟}}`。

    时间子消息按 **proto3 规范形**：小时=0 与 分钟=0 均**省略**（0:00 ⇒ 空子消息 `12 00`；
    对齐 2038/user 件的 `1a070d…1200`）。值=0 仍显式写出（否则该帧会退化成"无值帧"，
    与 f27/f28 的非数值组混淆）。
    """
    tt = []
    if int(hour):
        tt.append([1, 0, _ev(int(hour))])
    if int(minute):
        tt.append([2, 0, _ev(int(minute))])
    enc = _f32(value) if wt == 5 else _ev(int(value) & 0xFFFFFFFF)
    return [3, 2, emit([[1, wt, enc], [2, 2, emit(tt)]])]


def _group_set_time(cfg, field, base, points):
    """重写参数组 field = 组内 f1=1 + 基准 f2 + 时点表(repeated f3)。

    points = [(小时, 分钟, 值), …]。值线型（f32 / uint32 ARGB）**从现有组自动探测**：
    先看基准 f2 的线型，无则看关键帧 f1 的线型。
    """
    nd = _group_of(cfg, field)
    g = parse(nd[2], strict=False)
    wt = None
    for n in g:
        if n[0] == 2:
            wt = n[1]
            break
    if wt not in (5, 0):
        for n in g:
            if n[0] == 3:
                for kf_f, kf_w, _ in parse(n[2], strict=False):
                    if kf_f == 1:
                        wt = kf_w
                        break
                if wt in (5, 0):
                    break
    if wt not in (5, 0):
        raise ValueError(f"f{field} 值线型未定（wt={wt}），拒绝改写")
    out = [[G_TIME_FLAG, 0, _ev(1)],
           [2, wt, _f32(base) if wt == 5 else _ev(int(base) & 0xFFFFFFFF)]]
    for h, m, val in points:
        out.append(_kf_node(val, h, m, wt))
    nd[2] = emit(out)


def _payload_apply_time(payload, time_switch, time_curve):
    """在整段 f75 载荷上：设「随时间自动切换」总开关 + 逐组重写时点表（并置组内 f1=1）。"""
    t = parse(payload, strict=False)
    a_node = first(t, 1)
    a = parse(a_node[2], strict=False)
    cfg_node = first(a, 1)
    cfg = parse(cfg_node[2], strict=False)
    if time_switch is not None:
        _set_time_switch(cfg, time_switch)
    if time_curve:
        for fld in sorted(time_curve):
            spec = time_curve[fld]
            _group_set_time(cfg, int(fld), spec["base"], spec["pts"])
    set_body(cfg_node, cfg)
    set_body(a_node, a)
    return emit(t)


def _direct_payload(base_payload, *, sun=None, moon=None, light_color=None,
                    sky=None, ambient=None, fog=None, night_flag=True,
                    weather_fog=False, bind_targets=False, fog_color=None,
                    fog_far_dist=None, fog_set=None, fog_block_hex=None,
                    time_switch=None, time_curve=None):
    """取真实样本底座 payload，仅覆写已解码字段；未指定字段保持真实样本字节。

    weather_fog  = 是否启用「雾」（f75.f1.f3 天气配置；移植自用户件，见 WEATHER_FOG_HEX）
    bind_targets = 是否写入「生效目标/参考时间点」（f75.f1.f1 的 repeated f1，移植自用户件）
    fog_color    = 雾色 ARGB uint32（仅 weather_fog=True 时有效；改 f51.f15/f16/f20 的 base）
    fog_far_dist = 远雾点距离(m)（仅 weather_fog=True 时有效；改 f51.f17 的 base+关键帧）
    """
    """取真实样本底座 payload，仅覆写已解码字段；未指定字段保持真实样本字节。"""
    t = parse(base_payload, strict=False)
    a_node = first(t, 1)
    a = parse(a_node[2], strict=False)
    cfg_node = first(a, 1)
    cfg = parse(cfg_node[2], strict=False)

    def msg(f):
        nd = first(cfg, f)
        if nd is None or nd[1] != 2:
            raise ValueError(f"底座缺字段 f{f}（无法直写）")
        return parse(nd[2], strict=False), nd

    if sun is not None:
        ch, nd = msg(F_SUN); _set_f2(ch, _f32(sun), 5); nd[2] = emit(ch)
    if moon is not None:
        ch, nd = msg(F_MOON); _set_f2(ch, _f32(moon), 5); nd[2] = emit(ch)
    if light_color is not None:
        ch, nd = msg(F_LIGHT); _set_f2(ch, _ev(light_color & 0xFFFFFFFF), 0); nd[2] = emit(ch)
    if sky is not None:
        for f, c in zip(F_SKY, sky):
            ch, nd = msg(f); _set_f2(ch, _ev(c & 0xFFFFFFFF), 0); nd[2] = emit(ch)
    if ambient is not None:
        for f, c in zip(F_AMBIENT, ambient):
            ch, nd = msg(f); _set_f2(ch, _ev(c & 0xFFFFFFFF), 0); nd[2] = emit(ch)
    if fog is not None:
        ch, nd = msg(F_FOG); _set_f2(ch, _ev(fog & 0xFFFFFFFF), 0); nd[2] = emit(ch)
    _ensure_flag(cfg, F_NIGHT, night_flag)
    if bind_targets is not None:
        _set_targets(cfg, bind_targets)
    if time_switch is not None:
        _set_time_switch(cfg, time_switch)
    if time_curve:
        for fld in sorted(time_curve):
            spec = time_curve[fld]
            _group_set_time(cfg, int(fld), spec["base"], spec["pts"])

    set_body(cfg_node, cfg)
    if weather_fog is not None:
        _set_weather(a, weather_fog, fog_color, fog_far_dist, fog_set, fog_block_hex)
    set_body(a_node, a)
    return emit(t)


def _rewrite_payload(entry_nodes, raw_payload_hex=None, **kw):
    """把条目里 comp70 的 f75 载荷替换为目标字节（其余条目字节不动）。

    raw_payload_hex 给了则**整段移植**该 f75 载荷（不逐字段改写），
    用于「收用户手调环境为正典」（案例 #81）。
    """
    out = []
    for f, wt, body in entry_nodes:
        if f == 4 and wt == 2:
            cn = parse(body, strict=False)
            if _gi(cn, 1) == 70:
                new = []
                for cf, cwt, cb in cn:
                    if cf in (75, 80):
                        if raw_payload_hex is not None:
                            new.append([cf, 2, bytes.fromhex(raw_payload_hex)])
                        else:
                            new.append([cf, 2, _direct_payload(cb, **kw)])
                    else:
                        new.append([cf, cwt, cb])
                out.append([4, 2, emit(new)])
                continue
        out.append([f, wt, body])
    return out


def _f6_reg():
    f2 = emit([[1, 2, b'root'], [3, 0, _ev(1)]])
    f5 = emit([[1, 0, _ev(RES_CAT_ENV)], [2, 0, _ev(ENV_GUID)]])
    f3 = emit([[1, 2, '默认'.encode('utf-8')], [3, 0, _ev(2)], [5, 2, f5]])
    return [1, 2, emit([[1, 0, _ev(ASSET_TYPE_ENV)], [2, 2, f2], [3, 2, f3]])]


def _install_env(level_name, new_entry, label, *, expect_payload=None, req=None,
                 level_f11f1=None):
    """把环境条目装进关卡（f15 就地替换/新建）+ f6 cat56 注册；产物 + 后验 V1-V5。

    level_f11f1 给了则同时写「关卡设置」f11 = {f1: <该字节>}（基础页签·时间设置；
    缺字段的关卡若不给则维持无 f11 = 全默认）。
    """
    v = core.current_version(level_name)
    src = core.version_path(level_name, v)
    if not src.exists():
        raise core.PreconditionError(f"当前版本文件缺失: {src}")

    # ---- 前置 P4：底座 roundtrip ----
    c = Container.load(str(src))
    if not roundtrip(c.proto):
        raise core.PreconditionError(f"底座 {src} 往返验证失败")

    # ---- 执行：合成 → state/tmp ----
    top = parse(c.proto, strict=False)
    f15_node = first(top, 15)
    if f15_node is not None:                      # f15 已达 → 就地替换环境条目
        f15_entries = parse(f15_node[2], strict=False)
        replaced = False
        for i, ent in enumerate(f15_entries):
            if ent[0] == 1 and _gi(parse(ent[2], strict=False), 1) == ENV_GUID \
                    and _gi(parse(ent[2], strict=False), 2) == ENV_TC:
                f15_entries[i] = new_entry
                replaced = True
        if not replaced:
            f15_entries.append(new_entry)
    else:                                          # f15 缺失 → 新建仅含此条
        f15_entries = [new_entry]
    f15_new = [15, 2, emit(f15_entries)]
    f11_new = (None if level_f11f1 is None
               else [LEVEL_F, 2, emit([[1, 2, level_f11f1]])])

    new_top, done15, done11 = [], False, (level_f11f1 is None)
    for f, wt, body in top:
        # 按字段序插入 f11（关卡设置）/ f15（资产库）
        if not done11 and f > LEVEL_F:
            new_top.append(f11_new)
            done11 = True
        if not done15 and f > 15:                  # 原无 f15 → 按字段序插入
            new_top.append(f15_new)
            done15 = True
        if f == LEVEL_F and wt == 2 and not done11:
            new_top.append(f11_new)
            done11 = True
            continue
        if f == 15 and wt == 2 and not done15:
            new_top.append(f15_new)
            done15 = True
            continue
        if f == 6 and wt == 2:
            entries = parse(body, strict=False)
            if not any(ent[0] == 1 and
                       _gi(parse(ent[2], strict=False), 1) == ASSET_TYPE_ENV
                       for ent in entries):
                entries.append(_f6_reg())          # f6 cat56 未注册才追加（幂等）
            new_top.append([6, 2, emit(entries)])
        else:
            new_top.append([f, wt, body])
    if not done11:
        new_top.append(f11_new)
    if not done15:
        new_top.append(f15_new)

    tmp = core.state_dir() / "tmp" / "env_set.gil"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    Container(2, emit(new_top)).save(str(tmp))

    # ---- 后验 V1-V5（独立重读产出） ----
    checks, fails = [], 0

    def rec(name, good, detail=""):
        nonlocal fails
        checks.append((f"{name}({detail})" if detail else name, "PASS" if good else "FAIL"))
        if not good:
            fails += 1

    oc = Container.load(str(tmp))
    rec("roundtrip_output", roundtrip(oc.proto))
    a = parse(c.proto, strict=False)
    b = parse(oc.proto, strict=False)
    fa = {f: first(a, f)[2] for f, wt, _ in a}
    fb = {f: first(b, f)[2] for f, wt, _ in b}
    rec("only_f6_f15_changed",
        all(fa[k] == fb[k] for k in (set(fa) & set(fb)) - {6, 15, LEVEL_F}) and
        (set(fb) - set(fa)) <= {15, LEVEL_F} and not (set(fa) - set(fb)))
    ea = [e for e in parse(fa[6], strict=False)]
    eb = [e for e in parse(fb[6], strict=False)]
    rec("f6_old_entries_kept", eb[:len(ea)] == ea, f"{len(ea)}→{len(eb)}")
    e = parse(first(parse(fb[15], strict=False), 1)[2], strict=False)
    rec("readback_guid_tc_name",
        _gi(e, 1) == ENV_GUID and _gi(e, 2) == ENV_TC and _env_name(e) == ENV_NAME)
    if expect_payload is not None:
        rec("payload_faithful", _env_payload(e) == expect_payload)
    if req is not None:
        cfg = _cfg_of(_env_payload(e))

        def rv(f):
            nd = first(cfg, f)
            return parse(nd[2], strict=False) if (nd is not None and nd[1] == 2) else None

        def r32(f):
            s = rv(f); n = first(s, 2) if s else None
            return struct.unpack('<f', n[2])[0] if (n is not None and n[1] == 5) else None

        def ri(f):
            s = rv(f); n = first(s, 2) if s else None
            return varint_value(n) if (n is not None and n[1] == 0) else None

        if req.get("sun") is not None:
            rec("readback_sun", r32(F_SUN) is not None and abs(r32(F_SUN) - req["sun"]) < 1e-4,
                f"{r32(F_SUN)}")
        if req.get("moon") is not None:
            rec("readback_moon", r32(F_MOON) is not None and abs(r32(F_MOON) - req["moon"]) < 1e-4,
                f"{r32(F_MOON)}")
        if "night_flag" in req:
            nf = first(cfg, F_NIGHT) is not None
            rec("readback_night_flag", nf == req["night_flag"], "on" if nf else "off")
        if req.get("sky") is not None:
            got = [ri(f) for f in F_SKY]
            rec("readback_sky", got == [c & 0xFFFFFFFF for c in req["sky"]],
                str([hex(g) if g is not None else None for g in got]))
        if req.get("ambient") is not None:
            got = [ri(f) for f in F_AMBIENT]
            rec("readback_ambient", got == [c & 0xFFFFFFFF for c in req["ambient"]],
                str([hex(g) if g is not None else None for g in got]))
        if req.get("light_color") is not None:
            got = ri(F_LIGHT)
            rec("readback_light_color", got == (req["light_color"] & 0xFFFFFFFF),
                hex(got) if got is not None else "None")
        if req.get("fog") is not None:
            got = ri(F_FOG)
            rec("readback_fog_f47", got == (req["fog"] & 0xFFFFFFFF),
                hex(got) if got is not None else "None")
        if req.get("fog_color") is not None and req.get("weather_fog"):
            ap = parse(_env_payload(e), strict=False)
            a1 = parse(first(ap, 1)[2], strict=False)
            w = first(a1, F_WEATHER)
            s51 = parse(first(parse(first(parse(w[2], strict=False), 2)[2],
                                    strict=False), 51)[2], strict=False)
            got = []
            for f in FOG_COLOR_FIELDS:
                nd = first(s51, f)
                grp = parse(nd[2], strict=False) if nd else []
                bn = first(grp, 2) if grp else None
                got.append(varint_value(bn) if (bn is not None and bn[1] == 0) else None)
            rec("readback_fog_color",
                got == [req["fog_color"] & 0xFFFFFFFF] * 3,
                str([hex(g) if g is not None else None for g in got]))
        if req.get("fog_far_dist") is not None and req.get("weather_fog"):
            ap = parse(_env_payload(e), strict=False)
            a1 = parse(first(ap, 1)[2], strict=False)
            w = first(a1, F_WEATHER)
            s51 = parse(first(parse(first(parse(w[2], strict=False), 2)[2],
                                    strict=False), 51)[2], strict=False)
            nd = first(s51, FOG_FAR_DIST)
            grp = parse(nd[2], strict=False) if nd else []
            bn = first(grp, 2) if grp else None
            got = struct.unpack('<f', bn[2])[0] if (bn is not None and bn[1] == 5) else None
            rec("readback_fog_far_dist",
                got is not None and abs(got - req["fog_far_dist"]) < 1e-4,
                f"{got}")
        if "weather_fog" in req:
            ap = parse(_env_payload(e), strict=False)
            a1 = parse(first(ap, 1)[2], strict=False)
            w = first(a1, F_WEATHER)
            wb = w[2] if w is not None else None
            if req["weather_fog"]:
                rec("readback_weather_fog_on",
                    wb == _fog_block(req.get("fog_color"), req.get("fog_far_dist"),
                                     req.get("fog_set"), req.get("fog_block_hex")),
                    f"{len(wb) if wb else 0}B")
                if req.get("fog_set"):
                    s51 = parse(first(parse(first(parse(wb, strict=False), 2)[2],
                                           strict=False), 51)[2], strict=False)
                    okall = True
                    for fld, want in req["fog_set"].items():
                        nd2 = first(s51, int(fld))
                        if nd2 is None:
                            okall = False
                            continue
                        if nd2[1] == 5:
                            got = struct.unpack('<f', nd2[2])[0]
                        elif nd2[1] == 2:
                            bn = first(parse(nd2[2], strict=False), 2)
                            got = struct.unpack('<f', bn[2])[0] if (bn is not None and bn[1] == 5) else None
                        else:
                            got = None
                        if got is None or abs(got - float(want)) > 1e-4:
                            okall = False
                    rec("readback_fog_set", okall, str(req["fog_set"]))
            else:
                rec("readback_weather_fog_off",
                    wb == bytes.fromhex(WEATHER_OFF_HEX),
                    wb.hex() if wb is not None else "None")
        if "bind_targets" in req:
            tgt = [n for n in cfg if n[0] == F_TARGETS]
            if req["bind_targets"]:
                rec("readback_targets_on",
                    len(tgt) == 8 and
                    emit(tgt) == bytes.fromhex(TARGETS_HEX), f"{len(tgt)}条")
            else:
                rec("readback_targets_off", len(tgt) == 0, f"{len(tgt)}条")
        if "time_switch" in req:
            ts = first(cfg, F_TIME_SWITCH)
            rec("readback_time_switch",
                (ts is not None) == bool(req["time_switch"]),
                "on" if ts is not None else "off")
        if req.get("time_curve"):
            bad = []
            for fld, spec in req["time_curve"].items():
                nd2 = first(cfg, int(fld))
                if nd2 is None or nd2[1] != 2:
                    bad.append(f"f{fld}:缺"); continue
                gg = parse(nd2[2], strict=False)
                if first(gg, G_TIME_FLAG) is None:
                    bad.append(f"f{fld}:无flag")
                base = first(gg, 2)
                if base is None:
                    bad.append(f"f{fld}:无base")
                nkf = len([n for n in gg if n[0] == 3])
                if nkf != len(spec["pts"]):
                    bad.append(f"f{fld}:kf{nkf}≠{len(spec['pts'])}")
            rec("readback_time_curve", not bad, str(bad) if bad else f"{len(req['time_curve'])}组")
        if "level_time" in req:
            f11r = first(b, LEVEL_F)
            got = None
            if f11r is not None and f11r[1] == 2:
                l1 = first(parse(f11r[2], strict=False), 1)
                if l1 is not None:
                    s1 = parse(l1[2], strict=False)
                    i17 = first(s1, LEVEL_TIME_INIT)
                    n18 = first(s1, LEVEL_TIME_SPEED)
                    got = (varint_value(i17) if (i17 is not None and i17[1] == 0) else None,
                           struct.unpack('<f', n18[2])[0]
                           if (n18 is not None and n18[1] == 5) else None)
            want = req["level_time"]
            rec("readback_level_time", got == want, f"{got} vs {want}")
    if fails:
        raise core.ModuleRejected(f"后验 {fails} 项 FAIL: " +
                                  " | ".join(n for n, s in checks if s == "FAIL"))
    checks.append(("env", label))

    return core.Result(ok=True, artifact=str(tmp), level=level_name,
                       value=str(core.version_path(level_name, v + 1)), checks=checks)


@core.module("env.set")
def set_environment(level_name: str, preset: str = "very_dark") -> core.Result:
    """把关卡环境设为指定档（整包移植官方具名预设）；产出新版本 .gil。"""
    # ---- 前置 P1-P3 ----
    if preset not in _PRESETS:
        raise core.PreconditionError(
            f"preset={preset!r} 非法（只认 {list(_PRESETS)}；源自真实样本具名预设）")
    preset_guid, preset_name = _PRESETS[preset]
    if core.current_version(level_name) <= 0:
        raise core.PreconditionError(f"关卡 {level_name} 无当前版本（先入库）")
    if _src_map_path() is None:
        raise core.PreconditionError(f"真实样本图 {SRC_MAP}.gil 不在位（无环境预设可移植）")
    entry = _extract_env_entry(preset_guid)
    if entry is None:
        raise core.PreconditionError(f"真实样本图缺预设 0x{preset_guid:x}（{preset_name}）")

    new_entry = [1, 2, emit(_rewrite_entry(entry))]
    return _install_env(level_name, new_entry, preset_name,
                        expect_payload=_env_payload(entry))


@core.module("env.direct")
def direct_environment(level_name: str, name: str, *, base: str = "very_dark",
                       sun=None, moon=None, light_color=None, sky=None,
                       ambient=None, fog=None, night_flag: bool = True,
                       weather_fog: bool = False, bind_targets: bool = False,
                       fog_color=None, fog_far_dist=None, fog_set=None,
                       fog_block_hex=None, base_payload_hex=None,
                       time_switch=None, time_curve=None, level_time=None) -> core.Result:
    """字段直写夜色档：取真实样本预设作底座，只覆写已解码字段（其余字节不动）。

    sun/moon        = 太阳/月亮亮度 f32（None=保持底座）
    light_color     = 受光颜色 uint32 ARGB（如 0xFF6EB7EA）
    sky             = 4 值 (上层向阳, 上层背阳, 下层向阳, 下层背阳)
    ambient         = 4 值 (环境顶, 环境侧, 环境地面, 光晕)
    fog             = f47 颜色 uint32 ARGB（★旧命名；实证非雾，见模块头）
    night_flag      = 是否置夜标记 f16（有月亮/星等）
    weather_fog     = 是否启用**真雾**（f75.f1.f3 天气配置=雾；整段移植用户件字节）
    bind_targets    = 是否写入**生效目标/参考时间点**（f75.f1.f1 的 repeated f1；移植用户件）
    fog_color       = 雾色 ARGB uint32（如 0xFF8394AA；仅在 weather_fog=True 时生效，
                      改雾块 f51 的 f15/f16/f20 三个颜色组 base——即「雾色」）
    fog_far_dist    = 远雾点距离(m)（如 200.0；仅在 weather_fog=True 时生效，改 f51.f17 的 base+关键帧
                      = 视野限制器：越小看得越近）
    time_switch     = 「随时间自动切换」总开关（True=写 cfg 顶层 f3=1；None/False 保持/去掉）
    time_curve      = {字段号: {"base": 基准值, "pts": [(小时,分钟,值), …]}} —— 逐组写时点表
                      并置组内 f1=1（该参数时间曲线生效）。色值用 uint32 ARGB，亮度用 float。
    level_time      = (初始时间点, 每秒流逝分钟) —— 写「关卡设置」f11.f1 的 f17/f18；
                      第二项 None ⇒ 不写 f18（字节面 = 0 = 不推进）。
    """
    if base not in _PRESETS:
        raise core.PreconditionError(f"base={base!r} 非法（只认 {list(_PRESETS)}）")
    if sky is not None and len(sky) != 4:
        raise core.PreconditionError("sky 需 4 值（上层向阳/上层背阳/下层向阳/下层背阳）")
    if ambient is not None and len(ambient) != 4:
        raise core.PreconditionError("ambient 需 4 值（顶/侧/地面/光晕）")
    if core.current_version(level_name) <= 0:
        raise core.PreconditionError(f"关卡 {level_name} 无当前版本（先入库）")
    if _src_map_path() is None:
        raise core.PreconditionError(f"真实样本图 {SRC_MAP}.gil 不在位（无直写底座）")
    base_guid, base_name = _PRESETS[base]
    entry = _extract_env_entry(base_guid)
    if entry is None:
        raise core.PreconditionError(f"真实样本图缺底座预设 0x{base_guid:x}（{base_name}）")

    if base_payload_hex is not None:              # 整段移植（收用户手调环境为正典）
        raw = bytes.fromhex(base_payload_hex)
        if time_switch is not None or time_curve:
            raw = _payload_apply_time(raw, time_switch, time_curve)
        if fog_color is not None:                 # 仅在移植载荷上换雾色（单变量）
            raw = _payload_fog_color(raw, fog_color)
        rewritten = _rewrite_payload(entry, raw_payload_hex=raw.hex())
        new_entry = [1, 2, emit(_rewrite_entry(rewritten))]
        req = {"time_switch": time_switch, "time_curve": time_curve,
               "level_time": level_time}
        return _install_env(level_name, new_entry, name, expect_payload=raw, req=req,
                            level_f11f1=(_level_f11f1(*level_time)
                                         if level_time is not None else None))

    rewritten = _rewrite_payload(entry, sun=sun, moon=moon, light_color=light_color,
                                 sky=sky, ambient=ambient, fog=fog, night_flag=night_flag,
                                 weather_fog=weather_fog, bind_targets=bind_targets,
                                 fog_color=fog_color, fog_far_dist=fog_far_dist,
                                 fog_set=fog_set, fog_block_hex=fog_block_hex,
                                 time_switch=time_switch, time_curve=time_curve)
    new_entry = [1, 2, emit(_rewrite_entry(rewritten))]
    req = {"sun": sun, "moon": moon, "light_color": light_color, "sky": sky,
           "ambient": ambient, "fog": fog, "night_flag": night_flag,
           "weather_fog": weather_fog, "bind_targets": bind_targets,
           "fog_color": fog_color, "fog_far_dist": fog_far_dist,
           "fog_set": fog_set, "fog_block_hex": fog_block_hex,
           "time_switch": time_switch, "time_curve": time_curve,
           "level_time": level_time}
    return _install_env(level_name, new_entry, name, req=req,
                        level_f11f1=(_level_f11f1(*level_time)
                                     if level_time is not None else None))


def _env_name(entry_nodes):
    for f, wt, body in entry_nodes:
        if f == 4 and wt == 2:
            cn = parse(body, strict=False)
            if _gi(cn, 1) == 1:
                m = parse(first(cn, 11)[2], strict=False)
                return first(m, 1)[2].decode('utf-8')
    return None
