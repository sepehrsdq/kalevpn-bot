from app.database import get_db
from app.utils import get_float_setting


def reward_referral_if_needed(referred_user_id, invoice_id):
    conn = get_db()

    ref_row = conn.execute(
        "SELECT referrer_id FROM users WHERE user_id=?",
        (referred_user_id,),
    ).fetchone()

    if not ref_row or not ref_row["referrer_id"]:
        conn.close()
        return None

    referrer_id = int(ref_row["referrer_id"])

    if referrer_id == int(referred_user_id):
        conn.close()
        return None

    exists = conn.execute(
        """
        SELECT id FROM referral_rewards
        WHERE referrer_id=? AND referred_user_id=?
        """,
        (referrer_id, referred_user_id),
    ).fetchone()

    if exists:
        conn.close()
        return None

    reward = get_float_setting("referral_reward", 0.25)

    if reward <= 0:
        conn.close()
        return None

    conn.execute(
        """
        INSERT INTO referral_rewards(referrer_id, referred_user_id, invoice_id, amount)
        VALUES(?,?,?,?)
        """,
        (referrer_id, referred_user_id, invoice_id, reward),
    )

    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (reward, referrer_id),
    )

    conn.commit()
    conn.close()

    return referrer_id, reward
