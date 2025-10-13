# --- START OF FILE shared/financial_utils.py (REVISED) ---

# FILE: shared/financial_utils.py

from typing import Dict, Union
# --- MODIFIED IMPORT ---
from database.crud import user as crud_user
# --- ----------------- ---

async def calculate_payment_details(user_id: int, total_price: Union[int, float]) -> Dict[str, Union[int, float, bool]]:
    """
    Calculates the final payment details by considering the user's wallet balance.
    This is the central payment calculation engine for the bot.

    Args:
        user_id: The Telegram user ID.
        total_price: The total price of the service or item.

    Returns:
        A dictionary containing:
        - 'total_price': The original total price.
        - 'wallet_balance': The current balance of the user's wallet.
        - 'paid_from_wallet': The amount that will be deducted from the wallet.
        - 'payable_amount': The remaining amount that needs to be paid via invoice.
        - 'has_sufficient_funds': True if the wallet balance covers the total price.
    """
    wallet_balance = await crud_user.get_user_wallet_balance(user_id)
    if wallet_balance is None:
        wallet_balance = 0

    # Convert total_price to float for consistent calculations
    total_price = float(total_price)
    
    if wallet_balance >= total_price:
        # User has enough funds to pay entirely from wallet
        paid_from_wallet = total_price
        payable_amount = 0
        has_sufficient_funds = True
    else:
        # User has insufficient funds, wallet balance will be used as a down payment
        paid_from_wallet = float(wallet_balance)
        payable_amount = total_price - float(wallet_balance)
        has_sufficient_funds = False

    return {
        "total_price": total_price,
        "wallet_balance": float(wallet_balance),
        "paid_from_wallet": paid_from_wallet,
        "payable_amount": payable_amount,
        "has_sufficient_funds": has_sufficient_funds
    }

# --- END OF FILE shared/financial_utils.py (REVISED) ---