from enum import Enum


class InvoiceCurrency(str, Enum):
    other = "other"
    FKWalletRUB = "FKWalletRUB"
    FKWalletUSD = "FKWalletUSD"
    FKWalletEUR = "FKWalletEUR"
    VISARUB = "VISARUB"
    Yoomoney = "Yoomoney"
    VISAUAH = "VISAUAH"
    MasterCardRUB = "MasterCardRUB"
    MasterCardUAH = "MasterCardUAH"
    Qiwi = "Qiwi"
    VISAEUR = "VISAEUR"
    MIR = "MIR"
    OnlineBank = "OnlineBank"
    USDTERC20 = "USDTERC20"
    USDTTRC20 = "USDTTRC20"
    BitcoinCash = "BitcoinCash"
    BNB = "BNB"
    DASH = "DASH"
    Dogecoin = "Dogecoin"
    ZCash = "ZCash"
    Monero = "Monero"
    Waves = "Waves"
    Ripple = "Ripple"
    Bitcoin = "Bitcoin"
    Litecoin = "Litecoin"
    Ethereum = "Ethereum"
    SteamPay = "SteamPay"
    Megafon = "Megafon"
    VISAUSD = "VISAUSD"
    PerfectMoneyUSD = "PerfectMoneyUSD"
    ShibaInu = "ShibaInu"
    QIWIAPI = "QIWIAPI"
    CardRUBAPI = "CardRUBAPI"
    GooglePay = "GooglePay"
    ApplePay = "ApplePay"
    Tron = "Tron"
    WebMoneyWMZ = "WebMoneyWMZ"
    VISAMASTERCARDKZT = "VISAMASTERCARDKZT"
    SBP = "SBP"
    PRIMEPAYMENTSRUB = "PRIMEPAYMENTSRUB"

    @staticmethod
    def get_id(currency: "InvoiceCurrency") -> int:
        currency_ids = {
            "FKWalletRUB": 1, "FKWalletUSD": 2, "FKWalletEUR": 3,
            "VISARUB": 4, "Yoomoney": 6, "VISAUAH": 7,
            "MasterCardRUB": 8, "MasterCardUAH": 9, "Qiwi": 10,
            "VISAEUR": 11, "MIR": 12, "OnlineBank": 13,
            "USDTERC20": 14, "USDTTRC20": 15, "BitcoinCash": 16,
            "BNB": 17, "DASH": 18, "Dogecoin": 19,
            "ZCash": 20, "Monero": 21, "Waves": 22,
            "Ripple": 23, "Bitcoin": 24, "Litecoin": 25,
            "Ethereum": 26, "SteamPay": 27, "Megafon": 28,
            "VISAUSD": 32, "PerfectMoneyUSD": 33, "ShibaInu": 34,
            "QIWIAPI": 35, "CardRUBAPI": 36, "GooglePay": 37,
            "ApplePay": 38, "Tron": 39, "WebMoneyWMZ": 40,
            "VISAMASTERCARDKZT": 41, "SBP": 42, "PRIMEPAYMENTSRUB": 43,
        }
        return currency_ids.get(currency.value, 0)

    @staticmethod
    def get_name_by_id(id: int) -> "InvoiceCurrency":
        id_to_currency = {
            1: InvoiceCurrency.FKWalletRUB, 2: InvoiceCurrency.FKWalletUSD,
            3: InvoiceCurrency.FKWalletEUR, 4: InvoiceCurrency.VISARUB,
            6: InvoiceCurrency.Yoomoney, 7: InvoiceCurrency.VISAUAH,
            8: InvoiceCurrency.MasterCardRUB, 9: InvoiceCurrency.MasterCardUAH,
            10: InvoiceCurrency.Qiwi, 11: InvoiceCurrency.VISAEUR,
            12: InvoiceCurrency.MIR, 13: InvoiceCurrency.OnlineBank,
            14: InvoiceCurrency.USDTERC20, 15: InvoiceCurrency.USDTTRC20,
            16: InvoiceCurrency.BitcoinCash, 17: InvoiceCurrency.BNB,
            18: InvoiceCurrency.DASH, 19: InvoiceCurrency.Dogecoin,
            20: InvoiceCurrency.ZCash, 21: InvoiceCurrency.Monero,
            22: InvoiceCurrency.Waves, 23: InvoiceCurrency.Ripple,
            24: InvoiceCurrency.Bitcoin, 25: InvoiceCurrency.Litecoin,
            26: InvoiceCurrency.Ethereum, 27: InvoiceCurrency.SteamPay,
            28: InvoiceCurrency.Megafon, 32: InvoiceCurrency.VISAUSD,
            33: InvoiceCurrency.PerfectMoneyUSD, 34: InvoiceCurrency.ShibaInu,
            35: InvoiceCurrency.QIWIAPI, 36: InvoiceCurrency.CardRUBAPI,
            37: InvoiceCurrency.GooglePay, 38: InvoiceCurrency.ApplePay,
            39: InvoiceCurrency.Tron, 40: InvoiceCurrency.WebMoneyWMZ,
            41: InvoiceCurrency.VISAMASTERCARDKZT, 42: InvoiceCurrency.SBP,
            43: InvoiceCurrency.PRIMEPAYMENTSRUB,
        }
        return id_to_currency.get(id, InvoiceCurrency.other)
