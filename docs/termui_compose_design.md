# TermUI Compose 模式落地方案

## 背景

Textual 的 `compose()` 用 `yield` 声明子组件，代码扁平、可读性强。当前 termui 全部通过构造函数 `children=[...]` 传参，深层嵌套时临时变量多、结构不够直观。

本方案在 termui 引入 `compose()` 生成器模式，**保持完全向后兼容**。

---

## 设计原则

1. **渐进式**：现有 `children=[...]` 写法不受影响
2. **最小侵入**：只改 `Component` 基类、3 个 layout 容器、`Application`
3. **统一心智模型**：Component 子类和 Application 都能用 `compose()`
4. **向后兼容**：`build_root()` 老 API 保留，与 `compose()` 共存

---

## 改动一：Component 基类 (`_component_base.py`)

### 新增 import

```python
from collections.abc import Iterable
from typing import Iterator
```

### 新增方法

```python
class Component(ABC):
    # ... 现有 __init__ 完全不动 ...

    def compose(self) -> Iterator["Component"]:
        """子类 yield 子组件，框架自动挂载到 self.children。

        默认空实现，保持向后兼容。
        """
        return
        yield

    def _mount_composed(self) -> None:
        """消费 compose() 生成器，append 并设置 parent。

        由 layout 容器在 super().__init__() 后显式调用，
        避免在基类 __init__ 中调用时子类属性尚未就绪。
        """
        for child in self.compose():
            if child not in self.children:
                self.children.append(child)
                child.parent = self
```

---

## 改动二：TabView (`_component_layouts.py`)

```python
def __init__(
    self,
    children: Optional[list[Component]] = None,       # ← 改 Optional
    shortcuts: Optional[dict[str, Component]] = None,
    start: Optional[Component] = None,
    on_switch: Optional[Callable[[Component], None]] = None,
    x: int = 1,
    y: int = 1,
    size: Optional[tuple[int, int]] = None,
) -> None:
    super().__init__(x, y, size)

    self._on_switch = on_switch

    # 1. 先放显式 children
    if children is not None:
        self.children = list(children)

    # 2. 再消费 compose()
    self._mount_composed()

    # 3. 统一 wire parent
    for child in self.children:
        if child.parent is not None and child.parent is not self:
            _logger.warning("Reparenting %s to TabView", type(child).__name__)
        child.parent = self

    # 4. 校验 shortcuts（此时 compose() children 已在列表中）
    self._shortcuts = dict(shortcuts) if shortcuts else {}
    for key, panel in self._shortcuts.items():
        if panel not in self.children:
            raise ComponentError(
                f"shortcuts['{key}'] -> {type(panel).__name__} not in children"
            )

    # 5. 校验 children 非空 + start
    if not self.children:
        raise ComponentError("children cannot be empty.")
    if start is None:
        start = self.children[0]
    if start not in self.children:
        raise ComponentError(
            f"start {type(start).__name__} not in children. "
            f"Available: {[type(c).__name__ for c in self.children]}."
        )
    self._active = start
    self._active.activate()
    _set_focus_chain(start)
```

**关键修复**：`start` 校验放在 `_mount_composed()` 之后，这样 `compose()` yield 的组件也能作为 `start`。

---

## 改动三：Column (`_component_layouts.py`)

```python
def __init__(
    self,
    children: Optional[Sequence[Component]] = None,   # ← 改 Optional
    heights: Optional[Sequence[Union[int, Literal["flex"]]]] = None,  # ← 改 Optional
    x: int = 1,
    y: int = 1,
    size: Optional[tuple[int, int]] = None,
) -> None:
    super().__init__(x, y, size)

    if children is not None:
        self.children = list(children)
    self._mount_composed()
    for child in self.children:
        child.parent = self

    self._heights = list(heights) if heights is not None else []

    # 若 heights 已传，立即校验长度
    if self._heights and len(self._heights) != len(self.children):
        raise ValueError(
            f"heights length mismatch: expected {len(self.children)}, "
            f"got {len(self._heights)}"
        )

def resize(self, size: tuple[int, int]) -> None:
    self._size = size
    width, total_h = size

    # 防御：heights 为空时自动分配 flex
    if not self._heights:
        self._heights = ["flex"] * len(self.children) if self.children else []

    heights = layout_flex(self._heights, total_h)
    # ... 后续不变
```

---

## 改动四：Row (`_component_layouts.py`)

同 `Column` 模式，`children` 和 `widths` 改 Optional，`resize()` 开头防御空 widths：

```python
def resize(self, size: tuple[int, int]) -> None:
    self._size = size
    width, height = size

    if not self._widths:
        self._widths = ["flex"] * len(self.children) if self.children else []

    widths = layout_flex(self._widths, width)
    # ... 后续不变
```

---

## 改动五：Application (`_application.py`)

### 新增 import

```python
from collections.abc import Iterable
```

### 新增 `compose()` + 改造 `_run_body()`

```python
class Application:
    # ... 现有代码 ...

    def compose(self) -> Iterator[Component]:
        """应用级 compose：yield 顶层组件，自动包成 Column。

        若未重写（默认空），回退到 build_root()。
        """
        return
        yield

    def build_root(self) -> Component:
        """旧 API：返回单个根组件。

        当 compose() 未重写时，_run_body() 会调用此方法。
        """
        raise NotImplementedError("Subclasses must implement build_root() or compose().")

    def _run_body(self) -> None:
        """Assemble root, create loop, and start TUI."""
        composed = list(self.compose())
        if composed:
            body = Column(children=composed)
        else:
            body = self.build_root()

        self._root = root = ComponentRoot(body)
        self._loop = _ApplicationEventLoop(root, self, **self._loop_kwargs)
        self.setup_root(root)
        try:
            self._loop.run()
        finally:
            root.destroy()
```

**行为规则**：

| 子类实现 | 实际行为 |
|---------|---------|
| 只重写了 `build_root()` | 走老路径，完全兼容 |
| 只重写了 `compose()` | yield 的组件被 `Column` 包裹（高度全 `"flex"`） |
| 两者都重写了 | `compose()` 优先，`build_root()` 被忽略 |

---

## 迁移示例：`app.py`

### Before（imperative）

```python
def build_root(self) -> Component:
    diff = DiffViewer()
    status = StatusPanel(display=diff, on_visual_mode_changed=..., git=self._git)
    branch = BranchPanel(..., git=self._git)
    commit = CommitPanel(display=diff, ..., git=self._git)
    tab = TabView(
        children=[status, branch, commit, diff],
        shortcuts={"1": status, "2": branch, "3": commit},
        start=status,
        on_switch=_on_tab_switch,
    )
    inspector = InspectorPanel()
    row = Row(children=[tab, inspector], widths=["flex", 0])
    header = Header(...)
    footer = AppFooter(...)
    return Column(children=[header, row, footer], heights=[2, "flex", 2])
```

### After（compose 风格）

```python
def compose(self):
    diff = DiffViewer()
    status = StatusPanel(display=diff, on_visual_mode_changed=..., git=self._git)
    branch = BranchPanel(..., git=self._git)
    commit = CommitPanel(display=diff, ..., git=self._git)

    yield Header(...)
    yield Row(
        children=[
            TabView(
                children=[status, branch, commit, diff],
                shortcuts={"1": status, "2": branch, "3": commit},
                start=status,
                on_switch=_on_tab_switch,
            ),
            InspectorPanel(),
        ],
        widths=["flex", 0],
    )
    yield AppFooter(...)
```

`_run_body()` 自动把 yield 结果包成 `Column`，高度全部 `"flex"`。若需要自定义顶层高度，继续用 `build_root()` 显式返回 `Column(heights=[...])`。

---

## 边界情况

| 场景 | 行为 |
|------|------|
| `build_root()` 返回单个 `Component` | 走老路径，完全兼容 |
| `compose()` 空实现 + `build_root()` 有实现 | 回退到 `build_root()` |
| `Column(children=[...], heights=[...])` | 老写法不变 |
| 子类重写 `compose()` + `__init__` 传 `children` | **两者合并**，显式在前，compose 补漏 |
| `compose()` yield 的 child 已在 `children` 列表 | 自动去重，不重复 append |
| `heights` 为 `None` 且 children 来自 `compose()` | `resize()` 时自动设为 `["flex"] * n` |
| `TabView.start` 是 `compose()` yield 的对象 | 支持，校验在 `_mount_composed()` 之后 |

---

## 混用规则（显式 children + compose）

```python
class MyPanel(Column):
    def compose(self):
        yield Header()
        yield Body()

# 方式一：纯 compose
MyPanel(heights=[2, "flex"])

# 方式二：纯显式
MyPanel(children=[Header(), Body()], heights=[2, "flex"])

# 方式三：混用（显式 1 个 + compose 补 1 个）
MyPanel(children=[Header()], heights=[2, "flex"])
# 最终 children == [Header(), Body()]
```

**注意**：混用时 `heights`/`widths` 长度必须与**总 children 数**匹配。

---

## 文件改动清单

| 文件 | 大约行数 | 说明 |
|------|---------|------|
| `_component_base.py` | +15 | `compose()` + `_mount_composed()` + imports |
| `_component_layouts.py` | ~45 | TabView/Column/Row children 改 Optional，加 mount，防空头 |
| `_application.py` | +12 | `compose()` + `_run_body()` 优先策略 |

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| `heights=[]` 导致 `resize()` 崩溃 | `Column/Row.resize()` 开头自动补全 `["flex"] * n` |
| `__iter__` 误判字符串/组件 | 用 `isinstance(result, Iterable)` 并显式排除 `str/bytes/Component` |
| `TabView.start` 在 mount 前校验失败 | 把 `start` 校验移到 `_mount_composed()` 之后 |
| 现有调用全部传了 `heights` | 搜索确认：`app.py`、`repo_cd_picker.py`、`_picker.py` 均显式传参，不受影响 |