from app.database import get_db


def award_trial_bonus_if_eligible(user_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT id
        FROM trial_services
        WHERE user_id=?
        AND bonus_claimed=0
        AND status IN ('TRIAL_ACTIVE','TRIAL_EXPIRED')
        AND bonus_expires_at IS NOT NULL
        AND datetime('now') <= datetime(bonus_expires_at)
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if not row:
        conn.close()
        return False, 0

    bonus_row = conn.execute(
        """
        SELECT value
        FROM settings
        WHERE key='trial_wallet_bonus'
        """
    ).fetchone()

    try:
        bonus = float(bonus_row["value"] if bonus_row else 0.10)
    except Exception:
        bonus = 0.10

    if bonus <= 0:
        conn.close()
        return False, 0

    conn.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id=?
        """,
        (bonus, user_id),
    )

    conn.execute(
        """
        UPDATE trial_services
        SET bonus_claimed=1,
            status='TRIAL_REWARDED',
            converted_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (row["id"],),
    )

    conn.commit()
    conn.close()

    return True, bonus
