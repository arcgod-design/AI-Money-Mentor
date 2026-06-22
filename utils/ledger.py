class LedgerSystem:
    @staticmethod
    def get_user_accounts(user_id):
        return []

    @staticmethod
    def get_account_summary(user_id):
        return {"total_balance": 0.0, "net_worth": 0.0}

    @staticmethod
    def create_account(user_id, account_data):
        pass

    @staticmethod
    def update_account(account_id, user_id, account_data):
        pass

    @staticmethod
    def delete_account(account_id, user_id):
        pass
        
    @staticmethod
    def add_transaction(user_id, transaction_data):
        pass

    @staticmethod
    def get_account_transactions(account_id, user_id, limit=50, offset=0):
        return []

    @staticmethod
    def get_user_transactions(user_id, limit=50, offset=0):
        return []
