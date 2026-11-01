"""새삼은행 - 로컬 SQLite 저장소

이 앱은 실제 돈을 옮기지 않습니다. 대신 "누가 누구에게 얼마를
정산해야 하는지"만 기록하는 장부(ledger) 역할을 합니다. 실제 송금은
카카오페이/토스/은행 앱으로 각자 진행하고, 이 앱에서는 요청을
만들고 완료 체크만 합니다.
"""
import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saesambank.db")


def set_db_dir(directory):
    """DB 파일 위치를 바꾼다 (안드로이드에서는 앱 전용 폴더를 써야 안전함)."""
    global DB_PATH
    os.makedirs(directory, exist_ok=True)
    DB_PATH = os.path.join(directory, "saesambank.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_no TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            pin TEXT NOT NULL,
            bank_name TEXT,
            bank_account_no TEXT,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_account TEXT NOT NULL,
            payer_account TEXT NOT NULL,
            amount INTEGER NOT NULL,
            memo TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _new_account_no(cur):
    cur.execute("SELECT COUNT(*) AS c FROM accounts")
    n = cur.fetchone()["c"]
    return f"110-{100000 + n:06d}"


def create_account(name, pin, bank_name="", bank_account_no=""):
    conn = get_conn()
    cur = conn.cursor()
    account_no = _new_account_no(cur)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO accounts (account_no, name, pin, bank_name, bank_account_no, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (account_no, name, pin, bank_name, bank_account_no, now),
    )
    conn.commit()
    conn.close()
    return account_no


def get_account(account_no):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE account_no = ?", (account_no,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def find_account_by_name(name):
    """이름으로 계좌를 찾음 (요청 대상 지정을 쉽게 하기 위함). 여러 명이면 첫 번째."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def authenticate(account_no, pin):
    acc = get_account(account_no)
    if acc and acc["pin"] == pin:
        return acc
    return None


def update_bank_info(account_no, bank_name, bank_account_no):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE accounts SET bank_name = ?, bank_account_no = ? WHERE account_no = ?",
        (bank_name, bank_account_no, account_no),
    )
    conn.commit()
    conn.close()


def create_settlement(requester_account, payer_account, amount, memo=""):
    """정산 요청 생성. requester = 돈을 받아야 하는 사람, payer = 돈을 보내야 하는 사람."""
    if amount <= 0:
        return False, "금액은 0보다 커야 합니다.", None
    if requester_account == payer_account:
        return False, "본인에게는 요청할 수 없습니다.", None

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM accounts WHERE account_no = ?", (requester_account,))
    if not cur.fetchone():
        conn.close()
        return False, "요청하는 계좌를 찾을 수 없습니다.", None

    cur.execute("SELECT * FROM accounts WHERE account_no = ?", (payer_account,))
    if not cur.fetchone():
        conn.close()
        return False, "상대방 계좌를 찾을 수 없습니다.", None

    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO settlements (requester_account, payer_account, amount, memo, status, created_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        (requester_account, payer_account, amount, memo, now),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return True, "정산 요청이 생성되었습니다.", new_id


def complete_settlement(settlement_id):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE settlements SET status = 'completed', completed_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (now, settlement_id),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0


def get_settlement(settlement_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM settlements WHERE id = ?", (settlement_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending(account_no):
    """내가 관련된 미완료 정산 목록 (요청한 것 + 요청받은 것 모두)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM settlements
           WHERE (requester_account = ? OR payer_account = ?) AND status = 'pending'
           ORDER BY id DESC""",
        (account_no, account_no),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_history(account_no, limit=50):
    """완료된 정산 내역."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM settlements
           WHERE (requester_account = ? OR payer_account = ?) AND status = 'completed'
           ORDER BY completed_at DESC LIMIT ?""",
        (account_no, account_no, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_owed_to_me(account_no):
    """내가 받아야 할 총액 (미완료)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM settlements "
        "WHERE requester_account = ? AND status = 'pending'",
        (account_no,),
    )
    total = cur.fetchone()["total"]
    conn.close()
    return total


def get_i_owe(account_no):
    """내가 보내야 할 총액 (미완료)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM settlements "
        "WHERE payer_account = ? AND status = 'pending'",
        (account_no,),
    )
    total = cur.fetchone()["total"]
    conn.close()
    return total


def build_share_text(settlement):
    """카톡/문자로 붙여넣기 좋은 정산 요청 문구를 만듭니다."""
    requester = get_account(settlement["requester_account"])
    payer = get_account(settlement["payer_account"])
    amount = f"{settlement['amount']:,}"
    memo = settlement.get("memo") or ""

    lines = [f"[새삼은행 정산 요청] {requester['name']} → {payer['name']}"]
    if memo:
        lines.append(f"내용: {memo}")
    lines.append(f"금액: {amount}원")

    if requester.get("bank_name") and requester.get("bank_account_no"):
        lines.append(f"입금 계좌: {requester['bank_name']} {requester['bank_account_no']} ({requester['name']})")
    else:
        lines.append(f"{requester['name']}님에게 실제 계좌로 보내주세요.")

    return "\n".join(lines)
