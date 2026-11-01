"""새삼은행 (Saesam Bank) - Kivy mobile app

친구들끼리 "누가 누구에게 얼마를 정산해야 하는지" 기록하는 장부 앱.
실제 돈은 이 앱이 옮기지 않습니다 - 정산 요청을 만들면 실제 계좌
정보를 복사해서 카카오톡/문자로 보내고, 실제 이체는 은행 앱으로
직접 한 뒤 이 앱에서 "완료 처리"만 누르면 됩니다.
"""
from kivy.app import App
from kivy.factory import Factory
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.core.clipboard import Clipboard

import storage


class LoginScreen(Screen):
    def login(self):
        account_no = self.account_input.text.strip()
        pin = self.pin_input.text.strip()

        if not account_no or not pin:
            self.status_label.text = "계좌번호와 PIN을 입력해주세요."
            return

        acc = storage.authenticate(account_no, pin)
        if acc is None:
            self.status_label.text = "계좌번호 또는 PIN이 올바르지 않습니다."
            return

        self.status_label.text = ""
        app = App.get_running_app()
        app.current_account = account_no
        home = self.manager.get_screen("home")
        home.load_account()
        self.manager.current = "home"
        self.account_input.text = ""
        self.pin_input.text = ""


class RegisterScreen(Screen):
    def register(self):
        name = self.name_input.text.strip()
        pin = self.pin_input.text.strip()
        bank_name = self.bank_name_input.text.strip()
        bank_account_no = self.bank_account_input.text.strip()

        if not name:
            self.status_label.text = "이름을 입력해주세요."
            return
        if len(pin) < 4:
            self.status_label.text = "PIN은 4자리 이상이어야 합니다."
            return

        account_no = storage.create_account(name, pin, bank_name, bank_account_no)
        self.status_label.text = ""
        self.name_input.text = ""
        self.pin_input.text = ""
        self.bank_name_input.text = ""
        self.bank_account_input.text = ""

        login = self.manager.get_screen("login")
        login.status_label.text = f"계좌가 개설되었습니다: {account_no}"
        self.manager.current = "login"


class HomeScreen(Screen):
    def load_account(self):
        app = App.get_running_app()
        acc = storage.get_account(app.current_account)
        if acc is None:
            return
        self.name_label.text = f"{acc['name']} 님"
        self.account_label.text = acc["account_no"]
        owed = storage.get_owed_to_me(acc["account_no"])
        iowe = storage.get_i_owe(acc["account_no"])
        self.owed_label.text = f"{owed:,}원"
        self.iowe_label.text = f"{iowe:,}원"

    def on_pre_enter(self, *args):
        self.load_account()

    def go_request(self):
        self.manager.current = "request"

    def go_pending(self):
        self.manager.current = "pending"

    def go_history(self):
        self.manager.current = "history"

    def logout(self):
        App.get_running_app().current_account = None
        self.manager.current = "login"


class RequestScreen(Screen):
    def create_request(self):
        app = App.get_running_app()
        requester = app.current_account
        target_raw = self.to_input.text.strip()
        amount_text = self.amount_input.text.strip()
        memo = self.memo_input.text.strip()

        if not target_raw or not amount_text:
            self.status_label.text = "상대방과 금액을 입력해주세요."
            return

        try:
            amount = int(amount_text)
        except ValueError:
            self.status_label.text = "금액은 숫자로 입력해주세요."
            return

        # 계좌번호 형식이면 바로 찾고, 아니면 이름으로 찾는다.
        if target_raw.startswith("110-"):
            payer_acc = storage.get_account(target_raw)
        else:
            payer_acc = storage.find_account_by_name(target_raw)

        if payer_acc is None:
            self.status_label.text = "상대방 계좌를 찾을 수 없습니다."
            return

        ok, msg, _sid = storage.create_settlement(
            requester, payer_acc["account_no"], amount, memo
        )
        if not ok:
            self.status_label.text = msg
            return

        self.status_label.text = ""
        self.to_input.text = ""
        self.amount_input.text = ""
        self.memo_input.text = ""

        home = self.manager.get_screen("home")
        home.load_account()
        self.manager.current = "home"

    def on_pre_enter(self, *args):
        self.status_label.text = ""


def _left_label(**kwargs):
    """왼쪽 정렬되는 Label."""
    lbl = Label(halign="left", valign="middle", **kwargs)
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    return lbl


def _make_small_button(text, callback):
    btn = Factory.SmallActionButton(text=text)
    btn.bind(on_release=callback)
    return btn


def _settlement_row(settlement, my_account, on_complete=None, on_copy=None):
    """정산 대기/완료 항목 하나를 나타내는 위젯을 만든다."""
    is_requester = settlement["requester_account"] == my_account
    requester = storage.get_account(settlement["requester_account"])
    payer = storage.get_account(settlement["payer_account"])

    if is_requester:
        direction_text = f"{payer['name']}에게 받을 돈"
        color = (0.15, 0.45, 0.2, 1)
    else:
        direction_text = f"{requester['name']}에게 보낼 돈"
        color = (0.7, 0.2, 0.2, 1)

    memo = settlement.get("memo") or ""

    row = BoxLayout(orientation="vertical", size_hint_y=None, height="92dp",
                    padding=[10, 8, 10, 8], spacing="4dp")
    with row.canvas.before:
        Color(1, 1, 1, 1)
        rect = RoundedRectangle(pos=row.pos, size=row.size, radius=[10])

    def update_rect(instance, _value):
        rect.pos = instance.pos
        rect.size = instance.size

    row.bind(pos=update_rect, size=update_rect)

    top = BoxLayout(orientation="horizontal", size_hint_y=None, height="24dp")
    top.add_widget(_left_label(text=direction_text, font_size="13sp",
                               color=(0.2, 0.2, 0.2, 1)))
    amount_label = Label(text=f"{settlement['amount']:,}원", font_size="15sp",
                         bold=True, color=color, halign="right", size_hint_x=None,
                         width="100dp")
    amount_label.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    top.add_widget(amount_label)
    row.add_widget(top)

    memo_label = _left_label(text=memo, font_size="11sp", color=(0.55, 0.55, 0.55, 1),
                             size_hint_y=None, height="18dp")
    row.add_widget(memo_label)

    if settlement["status"] == "pending":
        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height="34dp",
                            spacing="8dp")
        btn_row.add_widget(_make_small_button("계좌 복사", lambda *_: on_copy(settlement)))
        btn_row.add_widget(_make_small_button("완료 처리", lambda *_: on_complete(settlement)))
        btn_row.add_widget(Label())
        row.add_widget(btn_row)
    else:
        completed_at = settlement.get("completed_at") or ""
        row.add_widget(_left_label(text=f"완료됨 · {completed_at}", font_size="10sp",
                                   color=(0.6, 0.6, 0.6, 1), size_hint_y=None,
                                   height="16dp"))

    return row


class PendingScreen(Screen):
    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        my_account = app.current_account
        self.pending_list.clear_widgets()
        rows = storage.get_pending(my_account)

        if not rows:
            self.pending_list.add_widget(
                Label(text="대기 중인 정산이 없습니다.", size_hint_y=None, height="40dp",
                      color=(0.5, 0.5, 0.5, 1))
            )
            return

        for settlement in rows:
            self.pending_list.add_widget(_settlement_row(
                settlement, my_account,
                on_complete=self._complete,
                on_copy=self._copy,
            ))

    def _complete(self, settlement):
        storage.complete_settlement(settlement["id"])
        self.refresh()
        self.manager.get_screen("home").load_account()

    def _copy(self, settlement):
        Clipboard.copy(storage.build_share_text(settlement))


class HistoryScreen(Screen):
    def on_pre_enter(self, *args):
        app = App.get_running_app()
        my_account = app.current_account
        self.history_list.clear_widgets()
        rows = storage.get_history(my_account)

        if not rows:
            self.history_list.add_widget(
                Label(text="완료된 정산 내역이 없습니다.", size_hint_y=None, height="40dp",
                      color=(0.5, 0.5, 0.5, 1))
            )
            return

        for settlement in rows:
            self.history_list.add_widget(_settlement_row(settlement, my_account))


class SaesamBankApp(App):
    current_account = None

    def build(self):
        storage.set_db_dir(self.user_data_dir)
        storage.init_db()
        self.title = "새삼은행"
        return self.root


if __name__ == "__main__":
    SaesamBankApp().run()
