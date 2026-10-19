import sys
import types
import typing
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


class u256(int):
    """GenLayer u256 primitive type."""

    def __new__(cls, val: int = 0):
        v = int(val)
        if v < 0 or v >= (1 << 256):
            raise OverflowError("u256 overflow or negative value")
        return super().__new__(cls, v)

    def __add__(self, other: Any) -> "u256":
        return u256(int(self) + int(other))

    def __sub__(self, other: Any) -> "u256":
        res = int(self) - int(other)
        if res < 0:
            raise OverflowError("u256 underflow")
        return u256(res)

    def __mul__(self, other: Any) -> "u256":
        return u256(int(self) * int(other))

    def __floordiv__(self, other: Any) -> "u256":
        return u256(int(self) // int(other))

    def __radd__(self, other: Any) -> "u256":
        return u256(int(other) + int(self))

    def __rsub__(self, other: Any) -> "u256":
        res = int(other) - int(self)
        if res < 0:
            raise OverflowError("u256 underflow")
        return u256(res)


class Address(str):
    """GenLayer Address primitive type."""

    def __new__(cls, val: str = "0x0000000000000000000000000000000000000000"):
        v = str(val).lower()
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError(f"Invalid Address format: {val}")
        return super().__new__(cls, v)


class TreeMap(Generic[K, V], dict):
    """GenLayer TreeMap persistent storage primitive."""
    pass


class DynArray(Generic[T], list):
    """GenLayer DynArray persistent storage primitive."""
    pass


def allow_storage(cls: Any) -> Any:
    """GenLayer @allow_storage decorator."""
    cls.__allow_storage__ = True
    return cls


class _ReturnWrapper:
    """Wrapper corresponding to gl.vm.Return."""

    def __init__(self, calldata: Any):
        self.calldata = calldata


class UserError(Exception):
    """User-facing contract revert in GenVM."""
    pass


class MessageContext:
    def __init__(self):
        self.contract_address = Address("0x9999999999999999999999999999999999999999")
        self.sender_address = Address("0x1111111111111111111111111111111111111111")
        self.origin_address = Address("0x1111111111111111111111111111111111111111")
        self.value = u256(0)
        self.chain_id = u256(61999)
        self.timestamp = 1700000000


@dataclass
class MockWebResponse:
    """Matches pinned GenVM v0.2.16 gl.nondet.web.Response (status, headers, body)."""
    status: int
    body: bytes | None
    headers: dict[str, bytes] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


@dataclass
class EmittedEthTransfer:
    recipient: Address
    value: u256


emitted_transfers: list[EmittedEthTransfer] = []
mock_web_responses: dict[str, MockWebResponse] = {}
mock_llm_responses: list[Callable[[str], Any]] = []
mock_llm_dict: dict[str, Any] = {}


class _WriteDecorator:
    def __call__(self, fn: Callable) -> Callable:
        fn.__gl_public__ = True
        fn.__gl_readonly__ = False
        fn.__gl_payable__ = False
        return fn

    def payable(self, fn: Callable) -> Callable:
        fn.__gl_public__ = True
        fn.__gl_readonly__ = False
        fn.__gl_payable__ = True
        return fn


class BaseContract:
    """Mock base class for gl.Contract that initializes TreeMap and DynArray storage descriptors."""

    def __init__(self):
        hints = typing.get_type_hints(type(self))
        for field_name, field_type in hints.items():
            origin = typing.get_origin(field_type)
            if origin is TreeMap or field_type is TreeMap:
                setattr(self, field_name, TreeMap())
            elif origin is DynArray or field_type is DynArray:
                setattr(self, field_name, DynArray())

    @property
    def balance(self) -> u256:
        inbound = int(getattr(self, "total_inbound_wei", 0))
        outbound = int(getattr(self, "total_outbound_wei", 0))
        return u256(max(0, inbound - outbound))

    @property
    def address(self) -> Address:
        return gl_mock.message.contract_address


class GenLayerMock:
    def __init__(self):
        self.message = MessageContext()
        self.Contract = BaseContract

        self.vm = types.SimpleNamespace(
            Return=_ReturnWrapper,
            UserError=UserError,
            run_nondet_unsafe=self._run_nondet_unsafe,
            run_nondet=self._run_nondet_unsafe,
        )

        self.nondet = types.SimpleNamespace(
            web=types.SimpleNamespace(
                get=self._web_get,
                Response=MockWebResponse,
            ),
            exec_prompt=self._exec_prompt,
        )

        self.public = types.SimpleNamespace(
            view=lambda fn: fn,
            write=_WriteDecorator(),
        )

        self.evm = types.SimpleNamespace(
            contract_interface=self._evm_contract_interface,
        )

    def _run_nondet_unsafe(self, leader_fn: Callable[[], Any], validator_fn: Callable[[Any], bool]) -> Any:
        leader_res = leader_fn()
        wrapped = _ReturnWrapper(leader_res)
        accepted = validator_fn(wrapped)
        if not accepted:
            raise UserError("CONSENSUS_VALIDATION_FAILED: Validator rejected leader envelope.")
        return leader_res

    def _web_get(self, url: str, *, headers: dict[str, str | bytes] = {}) -> MockWebResponse:
        if url in mock_web_responses:
            resp = mock_web_responses[url]
            if isinstance(resp, Exception):
                raise resp
            return resp
        return MockWebResponse(status=404, body=b'{"error": "Not Found"}')

    def _exec_prompt(self, prompt: str, **kwargs: Any) -> Any:
        for key, handler in mock_llm_dict.items():
            if key in prompt:
                return handler(prompt) if callable(handler) else handler
        for handler in mock_llm_responses:
            res = handler(prompt)
            if res is not None:
                return res
        raise RuntimeError(f"No mock LLM handler matched prompt:\n{prompt[:200]}")

    def _evm_contract_interface(self, cls: Any) -> Callable[[Address], Any]:
        class EvmProxy:
            def __init__(self, address: Address):
                self.address = Address(str(address))

            def emit_transfer(self, *, value: u256) -> None:
                if int(value) <= 0:
                    raise ValueError("Transfer value must be positive")
                emitted_transfers.append(EmittedEthTransfer(recipient=self.address, value=u256(value)))

        return EvmProxy


gl_mock = GenLayerMock()

genlayer_mod = types.ModuleType("genlayer")
genlayer_mod.gl = gl_mock
genlayer_mod.u256 = u256
genlayer_mod.Address = Address
genlayer_mod.TreeMap = TreeMap
genlayer_mod.DynArray = DynArray
genlayer_mod.allow_storage = allow_storage
genlayer_mod.__all__ = ["gl", "u256", "Address", "TreeMap", "DynArray", "allow_storage"]

sys.modules["genlayer"] = genlayer_mod
sys.modules["conftest"] = sys.modules[__name__]
sys.modules["tests.direct.conftest"] = sys.modules[__name__]

import pytest

ADMIN_ADDR = Address("0x1111111111111111111111111111111111111111")
RECIPIENT_A = Address("0x2222222222222222222222222222222222222222")
RECIPIENT_B = Address("0x3333333333333333333333333333333333333333")
STRANGER_ADDR = Address("0x4444444444444444444444444444444444444444")


@pytest.fixture(autouse=True)
def reset_genlayer_env():
    """Resets mocks before each direct-mode test."""
    emitted_transfers.clear()
    mock_web_responses.clear()
    mock_llm_responses.clear()
    mock_llm_dict.clear()
    gl_mock.message.sender_address = ADMIN_ADDR
    gl_mock.message.value = u256(0)
    gl_mock.message.timestamp = 1700000000
    yield
