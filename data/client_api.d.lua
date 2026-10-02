-- ============================================================================
-- client_api.d.lua — 千星奇域客户端脚本 API 全量签名
-- 内容: 官方《客户端控件 API 文档》的签名整理（逐条对应，附出处节号）
-- 用法: IDE attach 本文件获得补全；写脚本前查签名；亦可当 API 速查表。
-- 声明: API 语义版权归官方文档所有，本文件仅为接口签名的事实性整理。
-- ============================================================================

-- # 运行环境 (§三): Lua 5.3
-- 禁: string.dump / io.* / coroutine.* / os.*(留 time,date,clock,difftime) / debug.*(留 traceback)
-- 补: math.isnan(n), math.isinf(n)
-- 全局: script (Script), Enum, game (点号调用)

-- # 生命周期 (§1) — 运行时按固定名查找调用
function OnInit() end
function OnStart() end
function OnEnable() end
function OnDisable() end
function OnUpdate(dt) end              -- 不受关卡时停
function OnLevelUpdate(dt) end         -- 受关卡时停
function OnDestroy() end

-- # 全局API (§3)
---@return string
function typeof(value) end
function print(...) end
function printerr(...) end             -- 错误级日志, 不抛错不中断

-- # Color (§4)
---@return table ColorValue
function Color(r, g, b, a) end
function Color.FromRGB(r, g, b) end
function Color.FromRGBA(r, g, b, a) end
function Color.ToRGBA(colorValue) end  -- -> r, g, b, a

-- # Script (§5)
Script = {}
Script.alive = true                    -- [r] boolean
Script.scriptMappingId = 0             -- [r] integer
Script.object = nil                    -- [r] any 宿主对象
Script.path = ''                       -- [r] string
Script.enabled = true                  -- [rw] boolean
---@param paramName string
function script:GetParam(paramName) end
---@param funcName string @调用本脚本内全局函数(可传参)
function script:Invoke(funcName, ...) end
function script:EnableUpdate(enabled) end
---@param cb fun(signalName:string, signalParams:any[])
function script:RegisterServerSignalHandler(signalName, cb) end
function script:UnregisterServerSignalHandler(signalName) end
---@param entityType CustomVariableEntityType @Level|PlayerSelf|AvatarSelf
---@param cb fun(entityType, customVariableName) @值需 GetGlobalCustomVariableValue 再读
function script:RegisterCustomVariableChangedHandler(entityType, customVariableName, cb) end
function script:UnregisterCustomVariableChangedHandler(entityType, customVariableName) end

-- # game (§6)
---@param controlPrefabIndex integer @模板索引
---@param parent ClientUIBaseControl @仅"存为模板"的父节点可动态建
---@return ClientUIBaseControl
function game.InstantiateClientUIControl(controlPrefabIndex, parent) end
function game.DestroyClientUIControl(control) end
---@return ClientUIBaseControl @按运行时ID
function game.GetClientUIControl(controlId) end
function game.FindClientUIRoot(nodeName) end
---@return ClientUIBaseControl[]
function game.GetClientUIRoots() end
function game.GetUICanvasSize() end    -- -> x, y
function game.GetCursorUIPos() end     -- -> x, y
function game.GetDevice() end          -- -> Enum.Device
function game.SetControllerFocus(control) end
function game.GetControllerFocus() end
function game.GetControllerLeftStickAxis() end   -- -> h, v
function game.GetControllerRightStickAxis() end  -- -> h, v
---@param tweenDataTable table @{字段名=目标值}
---@return Tween
function game.Tween(object, tweenDataTable, duration) end
function game.TweenSequence() end
---@return ServerSignal
function game.ServerSignal(signalName) end
---@param entityType CustomVariableEntityType @支持列表/字典/结构体
function game.GetGlobalCustomVariableValue(entityType, customVariableName) end
function game.PauseLevelTime(pause) end   -- 单人; 不停脚本
function game.IsLevelTimePaused() end
function game.PlayAudio2D(audioId) end    -- -> instanceId
function game.StopAudio(audioInstanceId) end
function game.IsAudioAlive(audioInstanceId) end
function game.GetLanguageType() end
function game.GetStageMode() end          -- -> Enum.StageMode (Beyond|Classic)
function game.IsTestPlay() end
function game.GetText(textMapId) end
function game.PrintClientUITree() end

-- # Tween (§7) / TweenSequence (§8)
Tween = {}
function Tween:SetEase(easeType) end      -- 返回自身, 链式
function Tween:SetRelative(relative) end
function Tween:Play() end
function Tween:Pause() end
function Tween:Resume() end
function Tween:Restart() end
function Tween:Complete() end
function Tween:Kill(complete) end
function Tween:SetOnComplete(cb) end
function Tween:SetOnStepComplete(cb) end
function Tween:SetLoops(times) end        -- 负数=无限
TweenSequence = {}
function TweenSequence:Append(tween) end
function TweenSequence:AppendInterval(sec) end
function TweenSequence:AppendCallback(cb) end
function TweenSequence:Join(tween) end
function TweenSequence:Insert(time, tween) end
function TweenSequence:InsertCallback(time, cb) end
function TweenSequence:Play() end
function TweenSequence:SetOnComplete(cb) end
function TweenSequence:SetLoops(times) end

-- # ServerSignal (§9) — 链式: game.ServerSignal(n):AddString(s):SendSignal()
ServerSignal = {}
-- ⚠Add*返回值文档矛盾(§09表标"—", 实测有人链式): 用顺序调用三行式最稳:
-- local sig = game.ServerSignal("Name")  sig:AddInt(v)  sig:SendSignal()
---@param paramType Enum.ParamType
function ServerSignal:AddParam(paramType, paramValue) end
function ServerSignal:SendSignal() end
function ServerSignal:AddInt(v) end       function ServerSignal:AddIntList(v) end
function ServerSignal:AddFloat(v) end     function ServerSignal:AddFloatList(v) end
function ServerSignal:AddBool(v) end      function ServerSignal:AddBoolList(v) end
function ServerSignal:AddString(v) end    function ServerSignal:AddStringList(v) end
function ServerSignal:AddVector3(v) end   function ServerSignal:AddVector3List(v) end -- @{x,y,z}
function ServerSignal:AddGuid(v) end      function ServerSignal:AddGuidList(v) end
function ServerSignal:AddEntity(v) end    function ServerSignal:AddEntityList(v) end
function ServerSignal:AddPrefabId(v) end  function ServerSignal:AddPrefabIdList(v) end
function ServerSignal:AddConfigId(v) end  function ServerSignal:AddConfigIdList(v) end

-- # ClientUIBaseControl (§13) — 11 控件基类
ClientUIBaseControl = {}
ClientUIBaseControl.alive = true          -- [r]
ClientUIBaseControl.id = 0                -- [r] 运行时ID
ClientUIBaseControl.prefabIndex = 0       -- [r] 模板索引
ClientUIBaseControl.active = true         -- [r] SetActive 控制; 关=不可见+脚本停
ClientUIBaseControl.activeInHierarchy = true -- [r]
ClientUIBaseControl.visible = true        -- [r] SetVisible 控制; 不影响脚本
ClientUIBaseControl.name = ''             -- [rw]
ClientUIBaseControl.parent = nil          -- [rw]
ClientUIBaseControl.anchoredPositionX = 0 -- [rw] Tweenable
ClientUIBaseControl.anchoredPositionY = 0 -- [rw] Tweenable
ClientUIBaseControl.sizeDeltaX = 0        -- [rw] Tweenable
ClientUIBaseControl.sizeDeltaY = 0        -- [rw] Tweenable
ClientUIBaseControl.canControllerFocus = true -- [rw]
function ClientUIBaseControl:GetChildren() end
function ClientUIBaseControl:GetChild(name) end
function ClientUIBaseControl:FindChild(path) end
function ClientUIBaseControl:SetActive(active) end
function ClientUIBaseControl:SetVisible(visible) end
function ClientUIBaseControl:GetSiblingIndex() end
function ClientUIBaseControl:SetSiblingIndex(i) end
function ClientUIBaseControl:SetAsFirstSibling() end
function ClientUIBaseControl:SetAsLastSibling() end
function ClientUIBaseControl:GetAnchoredPosition() end  -- -> x, y
function ClientUIBaseControl:SetAnchoredPosition(x, y) end
function ClientUIBaseControl:GetSizeDelta() end
function ClientUIBaseControl:SetSizeDelta(x, y) end
function ClientUIBaseControl:GetAnchorMin() end
function ClientUIBaseControl:SetAnchorMin(x, y) end
function ClientUIBaseControl:GetAnchorMax() end
function ClientUIBaseControl:SetAnchorMax(x, y) end
function ClientUIBaseControl:GetPivot() end
function ClientUIBaseControl:SetPivot(x, y) end
function ClientUIBaseControl:GetLocalScale() end
function ClientUIBaseControl:SetLocalScale(x, y, z) end
function ClientUIBaseControl:GetLocalRotation() end
function ClientUIBaseControl:SetLocalRotation(x, y, z) end
function ClientUIBaseControl:GetScriptByPath(scriptPath) end
function ClientUIBaseControl:GetScript(scriptMappingId) end
function ClientUIBaseControl:GetScripts() end
---@param eventType Enum.KeyEventType
---@param cb fun():boolean @返回true=已处理, 拦截同容器其它控件
function ClientUIBaseControl:AddKeyEventListener(eventType, cb) end
function ClientUIBaseControl:RemoveKeyEventListener(eventType, cb) end
function ClientUIBaseControl:RemoveKeyEventListeners(eventType) end
function ClientUIBaseControl:RemoveAllKeyEventListeners() end
---@param eventType Enum.ControllerNavigationEventType
function ClientUIBaseControl:AddNavigationEventListener(eventType, cb) end
function ClientUIBaseControl:SetControllerNavigation(dir, mode, target) end
function ClientUIBaseControl:GetControllerNavigation(dir) end

-- # ClientUIImageControl (§14)
ClientUIImageControl = ClientUIBaseControl and {}
-- [rw] imageColor(Tweenable) imageType(enableMask) enableSoftEdge softEdgeMode
-- [rw] fillAmount(Tweenable) fillType fillHorizontalType fillVerticalType fillRadial90Type fillRadialType reverseMaskArea
-- 方法: SetImage(imageSource, imageId) SetSoftEdgeWidth(wx, wy)
--      SetFillUnused() SetFillHorizontal(t, amount) SetFillVertical(t, amount)
--      SetFillRadial90/180/360(t, amount)

-- # ClientUITextBoxControl (§15) — 对话渲染主力
ClientUITextBoxControl = ClientUIBaseControl and {}
-- [rw] text fontSize(Tweenable) fontColor(Tweenable) bgColor(Tweenable)
--      enableOutline outlineColor(Tweenable) horizontalAlignment verticalAlignment
--      adaptiveFontSize minimumFontSize(Tweenable)

-- # ClientUITextWindowControl (§16) — 可滚动文本
-- 文本框全套 + [rw] interactable showScrollBar

-- # ClientUIPresetButtonControl (§17) — 选项按钮主力
-- [rw] interactable clickAudioId raycastTarget
-- 方法: AddCursorEventListener(eventType, cb(CursorEventData)) RemoveCursorEventListener(...)
--      SimulateCursorClick()  -- 模拟 Down->Up->Click

-- # ClientUICursorEventAreaControl (§18) — 同按钮的光标事件面, raycastTarget [rw]

-- # CursorEventData (§19)
-- [r] dragging touchId
-- 方法: GetUIPos() GetPressUIPos() GetUIPosDelta() -- 各 -> x, y (画布左下原点)

-- # ClientUIGridScrollerControl (§20) — 虚拟列表(选项/背包/商店)
-- [r] itemCount scrollDirection layoutConstraint layoutConstraintFixedCount
-- [rw] itemPrefabIndex raycastTarget showScrollBar interactable scrollProgress(Tweenable)
-- 方法: RefreshItems(itemCount, cb(control, index)) GetItemIndex(control)
--      GetItemSize() GetItemSpacing() GetPadding() ScrollToItemAt(index, alignType)
--      GetContentLength()

-- # ClientUIKeyHintControl (§21): keyboardKeyCode controllerKeyCode [rw]
-- # ClientUIAnimationControl (§22): animationId playSoundEffect layer [rw] + Play/Stop
-- # ClientUIFullscreenAnimationControl (§23): animationId playSoundEffect [rw]
-- # ClientUIContainerControl (§24):
--   [rw] isolateNavigation disableKeyEventPassthrough disableCursorEventPassthrough
--   showCursor  -- ★常驻光标开关; CursorEvent 系方法需其为真 (纯鼠标2D玩法前提)
-- # ClientUIReferenceControl (§25): referencedPrefabIndex [r]

-- # 关键枚举 (§11)
Enum = {}
Enum.EaseType = { Linear=1, InSine=1, OutSine=1, InOutSine=1, InQuad=1, OutQuad=1,
  InOutQuad=1, InCubic=1, OutCubic=1, InOutCubic=1, InQuart=1, OutQuart=1, InOutQuart=1,
  InQuint=1, OutQuint=1, InOutQuint=1, InExpo=1, OutExpo=1, InOutExpo=1, InCirc=1,
  OutCirc=1, InOutCirc=1, InBack=1, OutBack=1, InOutBack=1, InElastic=1, OutElastic=1,
  InOutElastic=1, InBounce=1, OutBounce=1, InOutBounce=1 }  -- 31种, 值以运行时为准
Enum.CustomVariableEntityType = { Level=1, PlayerSelf=1, AvatarSelf=1 }
Enum.Device = { KeyboardAndMouse=1, Mobile=1, Controller=1, MobileController=1 }
Enum.StageMode = { Beyond=1, Classic=1 }
Enum.ParamType = { Entity=1, EntityList=1, Int=1, IntList=1, Bool=1, BoolList=1,
  Float=1, FloatList=1, String=1, StringList=1, Vector3=1, Vector3List=1, Guid=1,
  GuidList=1, ConfigId=1, PrefabId=1, ConfigIdList=1, PrefabIdList=1 }
Enum.CursorEventType = { CursorDown=1, CursorUp=1, CursorEnter=1, CursorExit=1,
  CursorDrag=1, CursorBeginDrag=1, CursorEndDrag=1, CursorClick=1 }
Enum.ScrollDirection = { Horizontal=1, Vertical=1 }
Enum.ScrollLayoutConstraint = { AutoWrap=1, Fixed=1 }
Enum.ScrollAlignType = { Bottom=1, Center=1, Top=1 }
Enum.ControllerNavigationDir = { Up=1, Down=1, Left=1, Right=1 }
Enum.ControllerNavigationEventType = { Confirm=1, Cancel=1, Focus=1, LostFocus=1 }
Enum.ControllerNavigationMode = { None=1, NearestControl=1, Specified=1 }
Enum.TextHorizontalAlignment = { Left=1, Middle=1, Right=1 }
Enum.TextVerticalAlignment = { Top=1, Middle=1, Bottom=1 }
Enum.ImageType = { Basic=1, Stretch=1 }
Enum.ImageSource = { StaticReference=1, Item=1, Equipment=1, Skill=1, UnitStatus=1,
  Faction=1, Currency=1, Prefab=1 }
Enum.ImageFillType = { Unused=1, Horizontal=1, Vertical=1, Radial90=1, Radial180=1, Radial360=1 }
Enum.UIAnimationLayer = { AboveAllControls=1, BelowAllControls=1 }
-- Enum.KeyboardKeyCode / ControllerKeyCode / KeyEventType: 全表见官方《客户端控件 API 文档》§26
-- (键盘全键+手柄含"奇匠按键1-14"自定义映射; 用时查文档切片)
