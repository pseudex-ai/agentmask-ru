"""The v6 mock backend under test: 78 tools, item-id tags, refusals, R-20/R-21.

The same discipline as `test_mock.py`: every check is shown a RIGHT input and,
where the rule is a refusal or a writer constraint, a WRONG one too. The seeded
world here is one `CaseV5` whose `PiiItem`s are the real values the mock returns
and whose `SeedRecord`s are the stored records the READ tools answer with — the
record id is the opaque key, the fields are the tool's own notation, and each
item's `where.path` binds it to the field the mock tags.
"""
import json
import random
import sys
import unicodedata

from bench.agentpii4 import pools
from bench.agentpii4.schema import (Case, Expectation, Locus, Message, PiiItem,
                                    Provenance, SeedRecord)
from bench.agentpii4.writer import Slot, WriterError, serialise
from bench.agentpii5 import gen_v6
from bench.agentpii5.contracts import CaseV5
from bench.agentpii5.mock import digits_of, snils_spaced
from bench.agentpii5.mock_v6 import (BackendV6, UNSCHEMED_NAMES, V6_NAMES,
                                     V6_SPECS, seed_backend_v6)
from bench.agentpii5.tools_v6 import TOOLS_V6

NOW = "2026-09-02"
STREAM = random.Random(20260922)
PHONE = "+79164021187"


def _inn() -> str:
    return pools.inn12_digits(STREAM)


def _snils() -> str:
    return snils_spaced(pools.snils_digits(STREAM))


def _snils_bare() -> str:
    return pools.snils_digits(STREAM)


def _v6(type_id: str) -> str:
    return gen_v6.generate(type_id, STREAM.randrange(1, 10**9))[0]


# Checksum-valid by CONSTRUCTION (pools / gen_v6), so the parsers accept them.
INN_WRITE = _inn()
OGRNIP_WRITE = _v6("OGRNIP")
INN_REQ = _inn()
OGRNIP_REQ = _v6("OGRNIP")
SNILS_CREDIT = _snils()          # spaced — credit_report_request subject.snils
SNILS_REMD = _snils_bare()       # bare — remd_documents_search patient_snils
SNILS_ELN = _snils_bare()        # bare — eln_get snils
SNILS_GKH = _snils()             # spaced — gis_gkh payer.snils
SNILS_HR = _snils()              # spaced — hr СтраховойНомерПФР
ENP_OMS = _v6("OMS_ENP")
ENP_RX = _v6("OMS_ENP")
CARD_READ = _v6("LOYALTY_CARD_NUMBER")
CARD_WRITE = _v6("LOYALTY_CARD_NUMBER")
ICCID_WRITE = _v6("ICCID")
ICCID_SUB = _v6("ICCID")
IMSI_SUB = _v6("IMSI")
IMEI_SUB = _v6("IMEI")
VIN_OSAGO = _v6("VIN")
VIN_EPTS = _v6("VIN")
EPTS = _v6("EPTS_NUMBER")
INN_CDEK = _inn()
INN_FNS = _inn()
INN_NPD = _inn()
INN_BUDGET = _inn()
INN_DWH = _inn()
INN_ARB = _inn()
INN_HR = _inn()
LOAN_UID_CREDIT = "1dcf884c-5f2a-4b3e-9d7a-6c5b4e3f2a1d-c"
LOAN_UID_DEBTOR = "2dcf884c-5f2a-4b3e-9d7a-6c5b4e3f2a1d-c"
LOAN_CONTRACT_DEBTOR = "МЗ-2025/118804"
UIN_FINES = "18810123456789012345"
UIN_CHARGES = "28810123456789012345"
PLATE_OSAGO = "Р777ТТ18"
PLATE_FINES = "А123ВС77"
STS_FINES = "77 12 345678"
DRIVER_LIC = "9912345678"
ELN_OGRN = "1027700132195"
ELN_LN = "900012345678"
IBAN_REQ = _v6("IBAN")
IBAN_WRITE = _v6("IBAN")
FSSP_IP_READ = _v6("FSSP_IP_NO")
COURT_CASE_READ = _v6("COURT_CASE_NO_SOU")
ESIA_OID_READ = _v6("ESIA_OID")
# --- the 12 WEB-STUDY both-ways tools -----------------------------------------
UIN_GMP = _v6("UIN")
UTILITY_ACCT = _v6("UTILITY_ACCOUNT")
IMEI_PROV = _v6("IMEI")
IMSI_OMNI = _v6("IMSI")
IP_API = _v6("IP_ADDRESS")
PNR_MANAGE = _v6("PNR")
METRICA_CID = _v6("METRICA_CLIENT_ID")
LOGIN_MOODLE = _v6("LOGIN")
MOBILE_AD = _v6("MOBILE_AD_ID")
MOBILE_AD_IFA = _v6("MOBILE_AD_ID")
APP_DEV = _v6("APP_DEVICE_ID")
MAC_DHCP = _v6("MAC")
ACCESS_PASS = _v6("ACCESS_PASS_NUMBER")
# --- the 16 final both-ways documented-procedure tools -------------------------
BIRTH_CERT_READ = _v6("BIRTH_CERT")
CIVIL_ACT_READ = _v6("CIVIL_ACT_CERT")
RESIDENCE_READ = _v6("RESIDENCE_PERMIT")
MILITARY_READ = _v6("MILITARY_ID")
CREDIT_CODE_READ = _v6("CREDIT_SUBJECT_CODE")
DMS_READ = _v6("DMS_POLICY")
KASKO_READ = _v6("KASKO_POLICY")
CLAIM_READ = _v6("INSURANCE_CLAIM_NUMBER")
COURT_UID_READ = _v6("COURT_CASE_UID")
EXEC_DOC_READ = _v6("EXEC_DOC_NO")
PTS_READ = _v6("PTS_NUMBER")
MEDCARD_READ = _v6("MEDCARD_NUMBER")
REFERRAL_READ = _v6("REFERRAL_NUMBER")
SCHOOL_CERT_READ = _v6("SCHOOL_CERT_NUMBER")
CONTRACT_READ = _v6("EMPLOYMENT_CONTRACT_NUMBER")
ETICKET_READ = _v6("E_TICKET_NUMBER")
# The audience_segment_upload result side echoes the uploaded customer id.
CDP_CID_ARG = "c-000184523"                               # == w_cdp (write record)

# The rubric account/bik pair is the tool's documented acceptance (`test_tools_v6`).
RUBLE_ACCOUNT = "40602810700000000025"
RUBLE_BIK = "049805746"
PAYROLL_ACCOUNT = "40817810515881399869"
ACCOUNT_BANK = "40817810515881399870"
# Values the WRITE items echo must not collide with a READ record's fields, or
# the by-value index calls them ambiguous and drops the tag. These stay on the
# READ side, distinct from the write side's «grom» person.
MARKETPLACE_NAME = "Зайцева Ольга"
MARKETPLACE_PHONE = "+79164445566"
OSAGO_READ = "АВС 9876543210"

# --- the seeded world: one record per READ tool + one empty "write" record -------
# (record_id, fields, [(item_id, type, identity, value, path), ...]) — the path
# is the seed field the item is bound to; "" for a WRITE item that only needs the
# by-value index for the echo tag.
RECORDS: tuple[tuple[str, dict[str, object], tuple[tuple[str, str, str, str, str], ...]], ...] = (
    # WRITE items live under one empty record: nothing is rendered from it, the
    # items are indexed by value so `_slot` can tag the echo.
    ("write", {}, (
        ("w_inn", "INN", "grom", INN_WRITE, ""),
        ("w_ogrnip", "OGRNIP", "grom", OGRNIP_WRITE, ""),
        ("w_iban", "IBAN", "grom", IBAN_WRITE, ""),
        ("w_ser", "PASSPORT", "grom", "4509", ""),
        ("w_num", "PASSPORT", "grom", "123456", ""),
        ("w_given", "NAME", "grom", "Марина", ""),
        ("w_surname", "NAME", "grom", "Громова", ""),
        ("w_name", "NAME", "grom", "Громова Марина", ""),
        ("w_phone", "PHONE", "grom", PHONE, ""),
        ("w_email", "EMAIL", "grom", "grom@mail.ru", ""),
        ("w_pavlova", "NAME", "grom", "Павлова Тамара", ""),
        ("w_pav_email", "EMAIL", "grom", "pavlova@mail.ru", ""),
        ("w_dob", "DOB", "grom", "14.03.1988", ""),
        ("w_pass_full", "PASSPORT", "grom", "4507 443565", ""),
        ("w_addr", "LOC", "grom", "г. Москва, ул. Тверская, д. 10, кв. 5", ""),
        ("w_rx_name", "NAME", "rx", "Иванов Пётр", ""),
        ("w_rx_enp", "OMS_ENP", "rx", ENP_RX, ""),
        ("w_rx_dob", "DOB", "rx", "1987-03-15", ""),
        ("w_presc", "PRESCRIPTION_NUMBER", "rx", "45 0012345678", ""),
        ("w_card", "LOYALTY_CARD_NUMBER", "grom", CARD_WRITE, ""),
        ("w_osago", "OSAGO_POLICY", "ins", "ХХХ 0123456789", ""),
        ("w_iccid", "ICCID", "grom", ICCID_WRITE, ""),
        ("w_guest", "NAME", "grom", "Сидоров Иван", ""),
        ("w_doc", "INTL_PASSPORT", "grom", "75 1234567", ""),
        ("w_tab", "EMPLOYEE_TAB_NUMBER", "grom", "004512", ""),
        ("w_pay_acc", "BANK_ACCOUNT", "grom", PAYROLL_ACCOUNT, ""),
        ("w_rub_acc", "BANK_ACCOUNT", "grom", RUBLE_ACCOUNT, ""),
        ("w_status", "NAME", "grom", "Открыт", ""),
        ("w_cdp", "CDP_CUSTOMER_ID", "grom", "c-000184523", ""),
        ("w_metrica", "METRICA_CLIENT_ID", "grom", METRICA_CID, ""),
    )),
    ("req-1", {"rq_inn": INN_REQ, "ogrnip": OGRNIP_REQ, "iban": IBAN_REQ,
               "rq_ident_doc_ser": "4501", "rq_ident_doc_num": "100001"}, (
        ("r_inn", "INN", "grom", INN_REQ, "rq_inn"),
        ("r_ogrnip", "OGRNIP", "grom", OGRNIP_REQ, "ogrnip"),
        ("r_iban", "IBAN", "grom", IBAN_REQ, "iban"),
        ("r_ser", "PASSPORT", "grom", "4501", "rq_ident_doc_ser"),
        ("r_num", "PASSPORT", "grom", "100001", "rq_ident_doc_num"),
    )),
    ("bc-1", {"account": ACCOUNT_BANK, "name": "Громова Марина Борисовна"}, (
        ("a_acc", "BANK_ACCOUNT", "grom", ACCOUNT_BANK, "account"),
        ("a_name", "NAME", "grom", "Громова Марина Борисовна", "name"),
    )),
    ("credit-1", {"passport": "4507 443564", "name": "Громова Марина Борисовна",
                  "birth_date": "1987-03-14", "loan_uid": LOAN_UID_CREDIT}, (
        ("c_pass", "PASSPORT", "grom", "4507 443564", "passport"),
        ("c_name", "NAME", "grom", "Громова Марина Борисовна", "name"),
        ("c_dob", "DOB", "grom", "1987-03-14", "birth_date"),
        ("c_uid", "LOAN_UID", "grom", LOAN_UID_CREDIT, "loan_uid"),
    )),
    ("debtor-1", {"contract_number": "12-345678/2025", "fio": "Тихонов Борис",
                  "birth_date": "14.03.1987", "phone": "+7 916 402-11-88",
                  "reg_address": "Удмуртская Респ, г Ижевск, ул Клубная, д 86, кв 12",
                  "loan_contract": LOAN_CONTRACT_DEBTOR, "loan_uid": LOAN_UID_DEBTOR,
                  "tp_fio": "Громов Олег Петрович", "tp_phone": "+7 912 555-40-10"}, (
        ("d_contract", "LOAN_CONTRACT_NUMBER", "grom", "12-345678/2025", "contract_number"),
        ("d_name", "NAME", "grom", "Тихонов Борис", "fio"),
        ("d_dob", "DOB", "grom", "14.03.1987", "birth_date"),
        ("d_phone", "PHONE", "grom", "+7 916 402-11-88", "phone"),
        ("d_addr", "LOC", "grom", "Удмуртская Респ, г Ижевск, ул Клубная, д 86, кв 12", "reg_address"),
        ("d_loan", "LOAN_CONTRACT_NUMBER", "grom", LOAN_CONTRACT_DEBTOR, "loan_contract"),
        ("d_uid", "LOAN_UID", "grom", LOAN_UID_DEBTOR, "loan_uid"),
        ("d_tp_fio", "NAME", "grom", "Громов Олег Петрович", "tp_fio"),
        ("d_tp_phone", "PHONE", "grom", "+7 912 555-40-10", "tp_phone"),
    )),
    ("eln-1", {"ln_code": ELN_LN, "snils": SNILS_ELN, "surname": "СМИРНОВА",
               "name": "ЕЛЕНА", "patronymic": "ПАВЛОВНА", "birthday": "1987-03-14",
               "serv_surname": "СМИРНОВ", "serv_name": "ПЁТР", "serv_birthday": "2019-05-20"}, (
        ("e_ln", "ELN_NUMBER", "grom", ELN_LN, "ln_code"),
        ("e_snils", "SNILS", "grom", SNILS_ELN, "snils"),
        ("e_surname", "NAME", "grom", "СМИРНОВА", "surname"),
        ("e_name", "NAME", "grom", "ЕЛЕНА", "name"),
        ("e_patr", "NAME", "grom", "ПАВЛОВНА", "patronymic"),
        ("e_dob", "DOB", "grom", "1987-03-14", "birthday"),
        ("e_serv_surname", "NAME", "grom", "СМИРНОВ", "serv_surname"),
        ("e_serv_name", "NAME", "grom", "ПЁТР", "serv_name"),
        ("e_serv_dob", "DOB", "grom", "2019-05-20", "serv_birthday"),
    )),
    ("remd-1", {"snils": SNILS_REMD, "document_number": "К-2026-00412",
                "fio": "Кузнецов Олег", "birth_date": "1987-03-14"}, (
        ("m_snils", "SNILS", "grom", SNILS_REMD, "snils"),
        ("m_doc", "MEDCARD_NUMBER", "grom", "К-2026-00412", "document_number"),
        ("m_name", "NAME", "grom", "Кузнецов Олег", "fio"),
        ("m_dob", "DOB", "grom", "1987-03-14", "birth_date"),
    )),
    ("oms-1", {"enp": ENP_OMS, "fam": "СМИРНОВА", "im": "ЕЛЕНА", "ot": "ПАВЛОВНА",
               "dr": "1987-03-14", "snils": SNILS_CREDIT}, (
        ("o_enp", "OMS_ENP", "grom", ENP_OMS, "enp"),
        ("o_fam", "NAME", "grom", "СМИРНОВА", "fam"),
        ("o_im", "NAME", "grom", "ЕЛЕНА", "im"),
        ("o_ot", "NAME", "grom", "ПАВЛОВНА", "ot"),
        ("o_dr", "DOB", "grom", "1987-03-14", "dr"),
        ("o_snils", "SNILS", "grom", SNILS_CREDIT, "snils"),
    )),
    ("oz-1", {"posting_number": "0123456789-0001-1", "name": MARKETPLACE_NAME,
              "addressee_name": "Ольга Зайцева",
              "address": "г Самара, ул Луговая, д 10"}, (
        ("z_name", "NAME", "grom", MARKETPLACE_NAME, "name"),
        ("z_addressee", "NAME", "grom", "Ольга Зайцева", "addressee_name"),
        ("z_addr", "LOC", "grom", "г Самара, ул Луговая, д 10", "address"),
    )),
    ("loyalty-1", {"card_number": CARD_READ, "last_name": "Лапина", "first_name": "Вера",
                   "middle_name": "Петровна", "birth_date": "1987-03-14",
                   "mobile_phone": "79163335544", "email": "lapina@mail.ru"}, (
        ("l_card", "LOYALTY_CARD_NUMBER", "grom", CARD_READ, "card_number"),
        ("l_last", "NAME", "grom", "Лапина", "last_name"),
        ("l_first", "NAME", "grom", "Вера", "first_name"),
        ("l_mid", "NAME", "grom", "Петровна", "middle_name"),
        ("l_dob", "DOB", "grom", "1987-03-14", "birth_date"),
        ("l_phone", "PHONE", "grom", "79163335544", "mobile_phone"),
        ("l_email", "EMAIL", "grom", "lapina@mail.ru", "email"),
    )),
    ("cdek-1", {"cdek_number": "1234567890", "name": "Волков Дмитрий",
                "passport_series": "4510", "passport_number": "654321",
                "passport_date_of_birth": "1987-03-14", "tin": INN_CDEK,
                "phone": "+79261119988", "address": "г. Ижевск, ул. Клубная, 85, кв. 12"}, (
        ("k_name", "NAME", "grom", "Волков Дмитрий", "name"),
        ("k_ser", "PASSPORT", "grom", "4510", "passport_series"),
        ("k_num", "PASSPORT", "grom", "654321", "passport_number"),
        ("k_dob", "DOB", "grom", "1987-03-14", "passport_date_of_birth"),
        ("k_inn", "INN", "grom", INN_CDEK, "tin"),
        ("k_phone", "PHONE", "grom", "+79261119988", "phone"),
        ("k_addr", "LOC", "grom", "г. Ижевск, ул. Клубная, 85, кв. 12", "address"),
    )),
    ("osago-1", {"series": "АВС", "osago_number": "9876543210", "plate": PLATE_OSAGO,
                 "vin": VIN_OSAGO}, (
        ("s_series", "OSAGO_POLICY", "grom", "АВС", "series"),
        ("s_number", "OSAGO_POLICY", "grom", "9876543210", "osago_number"),
        ("s_plate", "PLATE", "grom", PLATE_OSAGO, "plate"),
        ("s_vin", "VIN", "grom", VIN_OSAGO, "vin"),
    )),
    ("fines-1", {"sts": STS_FINES, "uin": UIN_FINES, "plate": PLATE_FINES}, (
        ("f_sts", "STS_NUMBER", "grom", STS_FINES, "sts"),
        ("f_uin", "UIN", "grom", UIN_FINES, "uin"),
        ("f_plate", "PLATE", "grom", PLATE_FINES, "plate"),
    )),
    ("epts-1", {"epts": EPTS, "vin": VIN_EPTS}, (
        ("p_epts", "EPTS_NUMBER", "grom", EPTS, "epts"),
        ("p_vin", "VIN", "grom", VIN_EPTS, "vin"),
    )),
    ("license-1", {"license": DRIVER_LIC}, (
        ("lic_num", "DRIVER_LICENSE", "grom", DRIVER_LIC, "license"),
    )),
    ("sub-1", {"msisdn": "79261112233", "family_name": "Смирнова", "given_name": "Елена",
               "middle_name": "Павловна", "birth_date": "1987-03-14",
               "passport": "9404 123456", "contract_number": "18-0412345",
               "personal_account": "418000123456", "iccid": ICCID_SUB,
               "imsi": IMSI_SUB, "imei": IMEI_SUB}, (
        ("u_msisdn", "PHONE", "grom", "79261112233", "msisdn"),
        ("u_family", "NAME", "grom", "Смирнова", "family_name"),
        ("u_given", "NAME", "grom", "Елена", "given_name"),
        ("u_mid", "NAME", "grom", "Павловна", "middle_name"),
        ("u_dob", "DOB", "grom", "1987-03-14", "birth_date"),
        ("u_pass", "PASSPORT", "grom", "9404 123456", "passport"),
        ("u_contract", "LOAN_CONTRACT_NUMBER", "grom", "18-0412345", "contract_number"),
        ("u_acc", "SUBSCRIBER_ACCOUNT", "grom", "418000123456", "personal_account"),
        ("u_iccid", "ICCID", "grom", ICCID_SUB, "iccid"),
        ("u_imsi", "IMSI", "grom", IMSI_SUB, "imsi"),
        ("u_imei", "IMEI", "grom", IMEI_SUB, "imei"),
    )),
    ("egrn-1", {"cadastral_number": "77:01:0001001:1234",
                "address": "Удмуртская Республика, г. Ижевск, ул. Клубная, д. 85, кв. 12",
                "holder": "Петров Сергей", "birth_date": "14.03.1987",
                "reg_number": "18:26:010203:1234-18/051/2021-3"}, (
        ("g_cad", "CADASTRAL_NUMBER", "grom", "77:01:0001001:1234", "cadastral_number"),
        ("g_addr", "LOC", "grom", "Удмуртская Республика, г. Ижевск, ул. Клубная, д. 85, кв. 12", "address"),
        ("g_name", "NAME", "grom", "Петров Сергей", "holder"),
        ("g_dob", "DOB", "grom", "14.03.1987", "birth_date"),
        ("g_reg", "NAME", "grom", "18:26:010203:1234-18/051/2021-3", "reg_number"),
    )),
    ("gkh-1", {"els": "60АА000593-01", "zhku_id": "60АА000593-01",
               "personal_account": "1234567890", "address": "г. Ижевск, ул. Клубная, д. 85, кв. 12",
               "fio": "Громова М. Б.", "snils": SNILS_GKH}, (
        ("h_els", "GIS_ZHKH_ELS", "grom", "60АА000593-01", "els"),
        ("h_zhku", "GIS_ZHKH_ELS", "grom", "60АА000593-01", "zhku_id"),
        ("h_pa", "UTILITY_ACCOUNT", "grom", "1234567890", "personal_account"),
        ("h_addr", "LOC", "grom", "г. Ижевск, ул. Клубная, д. 85, кв. 12", "address"),
        ("h_fio", "NAME", "grom", "Громова М. Б.", "fio"),
        ("h_snils", "SNILS", "grom", SNILS_GKH, "snils"),
    )),
    ("bk-1", {"name": "Анна", "surname": "Сидорова", "phone": "+79331112233",
              "email": "sidorova@mail.ru", "g_surname": "Сидоров", "g_name": "Иван",
              "g_birthdate": "1985-07-02", "g_series": "9404", "g_number": "654321"}, (
        ("b_name", "NAME", "grom", "Анна", "name"),
        ("b_surname", "NAME", "grom", "Сидорова", "surname"),
        ("b_phone", "PHONE", "grom", "+79331112233", "phone"),
        ("b_email", "EMAIL", "grom", "sidorova@mail.ru", "email"),
        ("b_g_surname", "NAME", "grom", "Сидоров", "g_surname"),
        ("b_g_name", "NAME", "grom", "Иван", "g_name"),
        ("b_g_dob", "DOB", "grom", "1985-07-02", "g_birthdate"),
        ("b_g_series", "PASSPORT", "grom", "9404", "g_series"),
        ("b_g_number", "PASSPORT", "grom", "654321", "g_number"),
    )),
    ("flight-1", {"pnr": "2ZYVAL", "date_of_birth": "1987-03-14",
                  "first_name": "MARINA", "last_name": "GROMOVA",
                  "passport_number": "761234568", "email": "m.gromova@example.ru",
                  "phone": "9164021187"}, (
        ("fl_pnr", "PNR", "grom", "2ZYVAL", "pnr"),
        ("fl_dob", "DOB", "grom", "1987-03-14", "date_of_birth"),
        ("fl_first", "NAME", "grom", "MARINA", "first_name"),
        ("fl_last", "NAME", "grom", "GROMOVA", "last_name"),
        ("fl_pass", "INTL_PASSPORT", "grom", "761234568", "passport_number"),
        ("fl_email", "EMAIL", "grom", "m.gromova@example.ru", "email"),
        ("fl_phone", "PHONE", "grom", "9164021187", "phone"),
    )),
    ("emp-1", {"tab_number": "005513", "description": "Морозов Пётр",
               "birth_date": "1987-03-14", "inn": INN_HR, "snils_pfr": SNILS_HR}, (
        ("em_tab", "EMPLOYEE_TAB_NUMBER", "grom", "005513", "tab_number"),
        ("em_name", "NAME", "grom", "Морозов Пётр", "description"),
        ("em_dob", "DOB", "grom", "1987-03-14", "birth_date"),
        ("em_inn", "INN", "grom", INN_HR, "inn"),
        ("em_snils", "SNILS", "grom", SNILS_HR, "snils_pfr"),
    )),
    ("res-1", {"last_name": "Лебедева", "first_name": "Ирина", "middle_name": "Игоревна",
               "birth_date": "1987-03-14", "phone": "+7 (916) 402-11-89",
               "email": "lebedev@mail.ru"}, (
        ("res_last", "NAME", "grom", "Лебедева", "last_name"),
        ("res_first", "NAME", "grom", "Ирина", "first_name"),
        ("res_mid", "NAME", "grom", "Игоревна", "middle_name"),
        ("res_dob", "DOB", "grom", "1987-03-14", "birth_date"),
        ("res_phone", "PHONE", "grom", "+7 (916) 402-11-89", "phone"),
        ("res_email", "EMAIL", "grom", "lebedev@mail.ru", "email"),
    )),
    ("arb-1", {"case_number": "А31-2840/2013", "number": "А31-2840/2013",
               "name": "ИП Громова Марина Борисовна", "inn": INN_ARB,
               "ogrnip": "324770000123455", "address": "г. Ижевск, ул. Клубная, д. 85, кв. 12"}, (
        ("ab_case", "ARBITRAZH_CASE_NO", "grom", "А31-2840/2013", "case_number"),
        ("ab_number", "ARBITRAZH_CASE_NO", "grom", "А31-2840/2013", "number"),
        ("ab_name", "NAME", "grom", "ИП Громова Марина Борисовна", "name"),
        ("ab_inn", "INN", "grom", INN_ARB, "inn"),
        ("ab_ogrnip", "OGRNIP", "grom", "324770000123455", "ogrnip"),
        ("ab_addr", "LOC", "grom", "г. Ижевск, ул. Клубная, д. 85, кв. 12", "address"),
    )),
    ("prob-1", {"deceased": "Николаев Виктор", "birth_date": "12.01.1941",
                "death_date": "03.05.2026", "case_number": "45/2026"}, (
        ("pr_name", "NAME", "grom", "Николаев Виктор", "deceased"),
        ("pr_dob", "DOB", "grom", "12.01.1941", "birth_date"),
        ("pr_dod", "DOB", "grom", "03.05.2026", "death_date"),
        ("pr_case", "COURT_CASE_NO_SOU", "grom", "45/2026", "case_number"),
    )),
    ("fns-1", {"fam": "Романов", "docno": "45 01 123456", "inn": INN_FNS}, (
        ("fn_fam", "NAME", "grom", "Романов", "fam"),
        ("fn_doc", "PASSPORT", "grom", "45 01 123456", "docno"),
        ("fn_inn", "INN", "grom", INN_FNS, "inn"),
    )),
    ("npd-1", {"inn": INN_NPD, "message": f"{INN_NPD} является плательщиком налога на профессиональный доход"}, (
        ("n_inn", "INN", "grom", INN_NPD, "inn"),
        ("n_msg", "INN", "grom", f"{INN_NPD} является плательщиком налога на профессиональный доход", "message"),
    )),
    ("budget-1", {"inn": INN_BUDGET, "uin": UIN_CHARGES, "payer_name": "ГРОМОВА МАРИНА БОРИСОВНА",
                  "payer_identifier": "1010000000094041234567"}, (
        ("bg_inn", "INN", "grom", INN_BUDGET, "inn"),
        ("bg_uin", "UIN", "grom", UIN_CHARGES, "uin"),
        ("bg_name", "NAME", "grom", "ГРОМОВА МАРИНА БОРИСОВНА", "payer_name"),
        ("bg_id", "PASSPORT", "grom", "1010000000094041234567", "payer_identifier"),
    )),
    ("diploma-1", {"series": "101805", "diploma_number": "0123456", "reg_number": "18-Б-0412",
                   "holder": "Громова Марина Борисовна"}, (
        ("dp_series", "DIPLOMA_NUMBER", "grom", "101805", "series"),
        ("dp_number", "DIPLOMA_NUMBER", "grom", "0123456", "diploma_number"),
        ("dp_reg", "DIPLOMA_NUMBER", "grom", "18-Б-0412", "reg_number"),
        ("dp_holder", "NAME", "grom", "Громова Марина Борисовна", "holder"),
    )),
    ("exam-1", {"reg_code": "EG-2025-123", "participant": "Гусев Никита"}, (
        ("ex_code", "EXAM_REG_CODE", "grom", "EG-2025-123", "reg_code"),
        ("ex_name", "NAME", "grom", "Гусев Никита", "participant"),
    )),
    ("lms-1", {"idnumber": "20-БИ-0412", "firstname": "Елена", "lastname": "Смирнова",
               "email": "m.gromova@example.ru", "phone1": "8 (3412) 45-67-89",
               "username": "gromova.m"}, (
        ("lm_id", "STUDENT_ID_NUMBER", "grom", "20-БИ-0412", "idnumber"),
        ("lm_first", "NAME", "grom", "Елена", "firstname"),
        ("lm_last", "NAME", "grom", "Смирнова", "lastname"),
        ("lm_email", "EMAIL", "grom", "m.gromova@example.ru", "email"),
        ("lm_phone", "PHONE", "grom", "8 (3412) 45-67-89", "phone1"),
        ("lm_login", "LOGIN", "grom", "gromova.m", "username"),
    )),
    ("dwh-1", {"client_fio": "Ковалёв Олег", "phone": "+79551112233", "inn": INN_DWH}, (
        ("dw_name", "NAME", "grom", "Ковалёв Олег", "client_fio"),
        ("dw_phone", "PHONE", "grom", "+79551112233", "phone"),
        ("dw_inn", "INN", "grom", INN_DWH, "inn"),
    )),
    ("ch-1", {"manager": "Соколова А.", "client": "Борисов Иван", "phone": "+79661112233"}, (
        ("ch_manager", "NAME", "grom", "Соколова А.", "manager"),
        ("ch_name", "NAME", "grom", "Борисов Иван", "client"),
        ("ch_phone", "PHONE", "grom", "+79661112233", "phone"),
    )),
    ("web-1", {"client_id": "250987654321098765", "ip": "95.165.12.34"}, (
        ("wb_client", "METRICA_CLIENT_ID", "grom", "250987654321098765", "client_id"),
        ("wb_ip", "IP_ADDRESS", "grom", "95.165.12.34", "ip"),
    )),
    ("fssp-1", {"name": "ФОМИНА АННА ПЕТРОВНА 14.03.1987 Г. ИЖЕВСК",
                "ip_number": FSSP_IP_READ, "case_number": COURT_CASE_READ,
                "last_name": "ФОМИНА", "first_name": "АННА"}, (
        ("fs_name", "NAME", "grom", "ФОМИНА АННА ПЕТРОВНА 14.03.1987 Г. ИЖЕВСК", "name"),
        ("fs_ip", "FSSP_IP_NO", "grom", FSSP_IP_READ, "ip_number"),
        ("fs_case", "COURT_CASE_NO_SOU", "grom", COURT_CASE_READ, "case_number"),
    )),
    ("court-1", {"case_number": COURT_CASE_READ, "name": "Истец Фомина А.П."}, (
        ("ct_case", "COURT_CASE_NO_SOU", "grom", COURT_CASE_READ, "case_number"),
        ("ct_name", "NAME", "grom", "Истец Фомина А.П.", "name"),
    )),
    ("esia-1", {"oid": ESIA_OID_READ}, (
        ("es_oid", "ESIA_OID", "grom", ESIA_OID_READ, "oid"),
    )),
    ("gmp-1", {"uin": UIN_GMP}, (
        ("gm_uin", "UIN", "grom", UIN_GMP, "uin"),
    )),
    ("util-1", {"personal_account": UTILITY_ACCT}, (
        ("ut_pa", "UTILITY_ACCOUNT", "grom", UTILITY_ACCT, "personal_account"),
    )),
    ("prov-1", {"imei": IMEI_PROV}, (
        ("pv_imei", "IMEI", "grom", IMEI_PROV, "imei"),
    )),
    ("omnihss-1", {"imsi": IMSI_OMNI}, (
        ("oh_imsi", "IMSI", "grom", IMSI_OMNI, "imsi"),
    )),
    ("ipapi-1", {"ip": IP_API}, (
        ("ip_ip", "IP_ADDRESS", "grom", IP_API, "ip"),
    )),
    ("fom-1", {"pnr": PNR_MANAGE}, (
        ("fo_pnr", "PNR", "grom", PNR_MANAGE, "pnr"),
    )),
    ("moodle-1", {"username": LOGIN_MOODLE}, (
        ("mo_login", "LOGIN", "grom", LOGIN_MOODLE, "username"),
    )),
    ("am-1", {"google_aid": MOBILE_AD, "ios_ifa": MOBILE_AD_IFA}, (
        ("am_aid", "MOBILE_AD_ID", "grom", MOBILE_AD, "google_aid"),
        ("am_ifa", "MOBILE_AD_ID", "grom", MOBILE_AD_IFA, "ios_ifa"),
    )),
    ("appdev-1", {"appmetrica_device_id": APP_DEV}, (
        ("ad_dev", "APP_DEVICE_ID", "grom", APP_DEV, "appmetrica_device_id"),
    )),
    ("dhcp-1", {"mac": MAC_DHCP}, (
        ("dh_mac", "MAC", "grom", MAC_DHCP, "mac"),
    )),
    ("uhppote-1", {"card_number": ACCESS_PASS}, (
        ("uh_card", "ACCESS_PASS_NUMBER", "grom", ACCESS_PASS, "card_number"),
    )),
    ("birth-cert-1", {"birth_cert_number": BIRTH_CERT_READ}, (
        ("bc_cert", "BIRTH_CERT", "grom", BIRTH_CERT_READ, "birth_cert_number"),
    )),
    ("civil-1", {"certificate_number": CIVIL_ACT_READ}, (
        ("ca_cert", "CIVIL_ACT_CERT", "grom", CIVIL_ACT_READ, "certificate_number"),
    )),
    ("rp-1", {"residence_permit": RESIDENCE_READ}, (
        ("rp_permit", "RESIDENCE_PERMIT", "grom", RESIDENCE_READ, "residence_permit"),
    )),
    ("mil-1", {"military_id": MILITARY_READ}, (
        ("ml_id", "MILITARY_ID", "grom", MILITARY_READ, "military_id"),
    )),
    ("csc-1", {"subject_code": CREDIT_CODE_READ}, (
        ("cs_code", "CREDIT_SUBJECT_CODE", "grom", CREDIT_CODE_READ, "subject_code"),
    )),
    ("dms-1", {"dms_policy": DMS_READ}, (
        ("dm_policy", "DMS_POLICY", "grom", DMS_READ, "dms_policy"),
    )),
    ("kasko-1", {"kasko_policy": KASKO_READ}, (
        ("ka_policy", "KASKO_POLICY", "grom", KASKO_READ, "kasko_policy"),
    )),
    ("claim-1", {"claim_number": CLAIM_READ}, (
        ("cl_claim", "INSURANCE_CLAIM_NUMBER", "grom", CLAIM_READ, "claim_number"),
    )),
    ("cuid-1", {"case_uid": COURT_UID_READ}, (
        ("cu_uid", "COURT_CASE_UID", "grom", COURT_UID_READ, "case_uid"),
    )),
    ("execdoc-1", {"writ_number": EXEC_DOC_READ}, (
        ("ed_writ", "EXEC_DOC_NO", "grom", EXEC_DOC_READ, "writ_number"),
    )),
    ("pts-1", {"pts_number": PTS_READ}, (
        ("pt_pts", "PTS_NUMBER", "grom", PTS_READ, "pts_number"),
    )),
    ("medcard-1", {"med_card_number": MEDCARD_READ}, (
        ("mc_card", "MEDCARD_NUMBER", "grom", MEDCARD_READ, "med_card_number"),
    )),
    ("referral-1", {"referral_id": REFERRAL_READ}, (
        ("rf_ref", "REFERRAL_NUMBER", "grom", REFERRAL_READ, "referral_id"),
    )),
    ("school-1", {"attestat_number": SCHOOL_CERT_READ}, (
        ("sc_cert", "SCHOOL_CERT_NUMBER", "grom", SCHOOL_CERT_READ, "attestat_number"),
    )),
    ("contract-1", {"employment_contract_number": CONTRACT_READ}, (
        ("ct_contract", "EMPLOYMENT_CONTRACT_NUMBER", "grom", CONTRACT_READ, "employment_contract_number"),
    )),
    ("eticket-1", {"ticket_number": ETICKET_READ}, (
        ("et_ticket", "E_TICKET_NUMBER", "grom", ETICKET_READ, "ticket_number"),
    )),
)


# (tool, arguments, expected form). The argument parses AND finds the seeded
# record, so the mock answers its "success" form.
RENDERS: tuple[tuple[str, dict[str, object], str], ...] = (
    ("crm_requisite_set", {"inn": INN_WRITE, "ogrnip": OGRNIP_WRITE, "iban": IBAN_WRITE,
                           "ident_doc": {"ser": "4509", "num": "123456"}}, "single"),
    ("crm_contact_upsert", {"first_name": "Марина", "last_name": "Громова",
                            "custom_fields_values": [{"field_id": 10001,
                                                      "values": [{"value": PHONE,
                                                                  "enum_code": "WORK"}]}]},
     "nested"),
    ("email_contacts_import", {"field_names": ["email", "phone", "name"],
                               "data": [["grom@mail.ru", PHONE, "Громова Марина"]]}, "single"),
    ("receipt_create", {"customer": {"full_name": "Павлова Тамара",
                                     "email": "pavlova@mail.ru", "phone": "79164021187",
                                     "inn": INN_WRITE}}, "single"),
    ("sms_send", {"destination": PHONE, "text": "Перезвоним завтра."}, "single"),
    ("ruble_transfer_create", {"payment_id": "pm-1",
                               "recipient": {"name": "Громова Марина",
                                             "account": RUBLE_ACCOUNT, "bik": RUBLE_BIK},
                               "amount": "1000.00", "purpose": "Перевод зарплаты"}, "single"),
    ("e_prescription_create", {"patient": {"fio": "Иванов Пётр", "birth_date": "1987-03-15",
                                           "oms_policy": ENP_RX},
                               "drug": "Амоксициллин", "dosage": "500 мг"}, "single"),
    ("loyalty_card_bind", {"customer": {"mobile_phone": "79164021187"},
                           "card_number": CARD_WRITE}, "single"),
    ("fiscal_receipt_create", {"external_id": "ext-1",
                               "receipt": {"items": [{"name": "Товар", "price": 100}],
                                           "client": {"name": "Павлова Тамара",
                                                      "email": "pavlova@mail.ru",
                                                      "phone": "79164021187",
                                                      "inn": INN_WRITE,
                                                      "birthdate": "14.03.1988",
                                                      "document_data": "4507 443565",
                                                      "address": "г. Москва, ул. Тверская, д. 10, кв. 5"}}},
     "single"),
    ("insurance_claim_create", {"applicant": {"fio": "Громова Марина",
                                              "birth_date": "1987-03-14",
                                              "passport": "4507 443564"},
                                "policy": "ХХХ 0123456789"}, "single"),
    ("sim_replace_request", {"msisdn": "79164021187", "fio": "Громова Марина",
                             "passport": "4507 443564", "new_iccid": ICCID_WRITE}, "single"),
    ("guest_arrival_notify", {"guest": {"last_name": "Сидоров", "first_name": "Иван",
                                        "citizenship": "RUS", "birth_date": "1987-03-14",
                                        "document": {"number": "75 1234567"}},
                              "stay": {"address": "г Ижевск, ул Клубная, д 85",
                                       "until": "2026-09-20"}}, "single"),
    ("payroll_card_registry", {"employees": [{"fio": "Громова Марина",
                                              "birth_date": "1987-03-14",
                                              "passport": "4507 443564",
                                              "tab_number": "004512"}]}, "list"),
    ("audience_segment_upload", {"segment_name": "Отток сентябрь",
                                 "file": {"rows": [{"phone": "79164021187",
                                                    "external_id": CDP_CID_ARG}] * 100},
                                 "hashed": "false"}, "single"),
    ("crm_requisite_get", {"inn": INN_REQ}, "single"),
    ("bank_accounts_list", {"client_id": "bc-1"}, "list"),
    ("credit_report_request", {"subject": {"last_name": "Громова", "first_name": "Марина",
                                           "birth_date": "1987-03-14",
                                           "passport": "4507 443564"},
                               "consent_id": "consent-1"}, "nested"),
    ("debtor_card_get", {"contract_number": "12-345678/2025"}, "nested"),
    ("eln_get", {"ogrn": ELN_OGRN, "ln_code": ELN_LN, "snils": SNILS_ELN}, "nested"),
    ("remd_documents_search", {"patient_snils": SNILS_REMD}, "list"),
    ("oms_policy_find", {"enp": ENP_OMS}, "single"),
    ("marketplace_order_get", {"posting_number": "0123456789-0001-1"}, "nested"),
    ("loyalty_customer_get", {"discount_card": CARD_READ}, "single"),
    ("cdek_order_info", {"cdek_number": "1234567890"}, "nested"),
    ("osago_policy_check", {"policy": OSAGO_READ}, "single"),
    ("traffic_fines_check", {"plate": PLATE_FINES, "sts": STS_FINES}, "list"),
    ("epts_status_get", {"epts_number": EPTS}, "single"),
    ("driver_license_check", {"license_number": "99 12 345678", "issue_date": "2019-06-11"}, "single"),
    ("subscriber_profile_get", {"msisdn": "79261112233"}, "nested"),
    ("egrn_extract_get", {"cadastral_number": "77:01:0001001:1234"}, "nested"),
    ("gis_gkh_account_get", {"els": "60АА000593-01"}, "single"),
    ("pms_booking_get", {"booking_id": "bk-1"}, "nested"),
    ("flight_order_get", {"flight_order_id": "2ZYVAL"}, "nested"),
    ("hr_employee_get", {"tab_number": "005513"}, "single"),
    ("resume_get", {"resume_id": "res-1"}, "nested"),
    ("arbitration_case_search", {"case_number": "А31-2840/2013"}, "list"),
    ("probate_case_search", {"fio": "Николаев Виктор"}, "list"),
    ("fns_inn_lookup", {"fam": "Романов", "nam": "Андрей", "bdate": "14.03.1987",
                        "doctype": "21", "docno": "45 01 123456"}, "single"),
    ("npd_status_check", {"inn": INN_NPD, "requestDate": "2026-09-02"}, "single"),
    ("budget_charges_find", {"payer_inn": INN_BUDGET}, "list"),
    ("diploma_registry_check", {"last_name": "Громова", "blank_series": "101805",
                                "blank_number": "0123456"}, "single"),
    ("exam_results_check", {"fio": "Гусев Никита", "region": "18",
                            "reg_code": "EG-2025-123"}, "list"),
    ("lms_user_get", {"field": "idnumber", "values": ["20-БИ-0412"]}, "list"),
    ("dwh_sql_query", {"sql": "SELECT * FROM t WHERE phone = '+79551112233'"}, "list"),
    ("bi_chart_export", {"chart_id": "ch-1", "result_format": "csv"}, "list"),
    ("web_visits_export", {"counter_id": "12345", "date1": "2026-01-01",
                           "date2": "2026-01-31", "fields": "ym:s:clientID,ym:s:ipAddress"},
     "free_text"),
    ("phone_clean", {"source": "8 (916) 402-11-87"}, "canon"),
    ("fssp_proceedings_search", {"region": "18", "last_name": "Фомина",
                                  "first_name": "Анна"}, "list"),
    ("court_document_fetch", {"court": "Индустриальный районный суд",
                               "case_number": COURT_CASE_READ}, "free_text"),
    ("esia_roles_get", {"prn_oid": ESIA_OID_READ}, "single"),
    ("gis_gmp_charge_find", {"SupplierBillID": UIN_GMP}, "list"),
    ("gis_gkh_utility_account_get", {"AccountID": UTILITY_ACCT}, "single"),
    ("device_provisioning_find", {"deviceIdentifier": IMEI_PROV}, "list"),
    ("omnihss_subscriber_get", {"imsi": IMSI_OMNI}, "single"),
    ("ip_api_lookup", {"query": IP_API}, "single"),
    ("flight_order_manage_get", {"flight_order_id": PNR_MANAGE}, "nested"),
    ("metrica_offline_conversion_upload", {"ClientId": METRICA_CID}, "single"),
    ("moodle_user_by_username", {"field": "username", "values": [LOGIN_MOODLE]}, "list"),
    ("appmetrica_event_import", {"google_aid": MOBILE_AD}, "single"),
    ("appmetrica_device_id_lookup", {"appmetrica_device_id": APP_DEV}, "single"),
    ("mikrotik_dhcp_lease_get", {"mac-address": MAC_DHCP}, "single"),
    ("uhppote_card_get", {"cardNumber": ACCESS_PASS}, "single"),
    ("birth_cert_fetch", {"birth_cert_number": BIRTH_CERT_READ}, "single"),
    ("civil_act_fetch", {"certificate_number": CIVIL_ACT_READ}, "single"),
    ("residence_permit_check", {"residence_permit": RESIDENCE_READ}, "single"),
    ("military_id_register", {"military_id": MILITARY_READ}, "single"),
    ("credit_subject_check", {"subject_code": CREDIT_CODE_READ}, "single"),
    ("dms_policy_find", {"dms_policy": DMS_READ}, "single"),
    ("kasko_policy_find", {"kasko_policy": KASKO_READ}, "single"),
    ("insurance_claim_status", {"claim_number": CLAIM_READ}, "single"),
    ("court_case_fetch", {"case_uid": COURT_UID_READ}, "single"),
    ("exec_doc_check", {"writ_number": EXEC_DOC_READ}, "single"),
    ("pts_vehicle_get", {"pts_number": PTS_READ}, "single"),
    ("medcard_lookup", {"med_card_number": MEDCARD_READ}, "single"),
    ("referral_find", {"referral_id": REFERRAL_READ}, "single"),
    ("school_cert_verify", {"attestat_number": SCHOOL_CERT_READ}, "single"),
    ("employment_contract_get", {"employment_contract_number": CONTRACT_READ}, "single"),
    ("e_ticket_issue", {"ticket_number": ETICKET_READ}, "single"),
)


def _case() -> CaseV5:
    items: list[PiiItem] = []
    seeds: list[SeedRecord] = []
    for record_id, fields, item_specs in RECORDS:
        pii_ids: list[str] = []
        for item_id, typ, identity, value, path in item_specs:
            items.append(PiiItem(item_id, typ, identity, value, value, {},
                                 Locus("seed", -1, 0, 0, record_id, path),
                                 "required", False, False))
            pii_ids.append(item_id)
        seeds.append(SeedRecord(record_id, "v6", dict(fields), tuple(pii_ids)))
    base = Case(
        id="v6-hand-1", kind="lookup_list", register="chat",
        provenance=Provenance("synthetic", "hand", "test_mock_v6", "case", "fixed", 1.0, "none"),
        cluster=f"PHONE:{PHONE}", conversation_id="conv-v6", now=NOW,
        messages=(Message("system", "Ты оператор.", None, ""),
                  Message("user", "Сделай вызов.", None, "")),
        tools=tuple(V6_NAMES), seed_records=tuple(seeds), pii=tuple(items),
        plain=(), negatives=(), expects=Expectation((), "grom", (), (), ()),
        trace=(), note="")
    return CaseV5(base=base, behaviour="single", hops=(), returns=(), forced=(),
                  memory=(), pick=None, branch=None, loop=None, rag=None, document=None,
                  has_result=False, streaming=False, revised_from_v4=False, v6=None)


def _values_at(node: object, path: str) -> list[object]:
    """Every leaf at a dotted path, `[]` erased and walked into arrays."""
    steps = path.split(".")

    def collect(cur: object, index: int) -> list[object]:
        if index == len(steps):
            return [] if isinstance(cur, (dict, list)) else [cur]
        step = steps[index]
        if step.endswith("[]"):
            key = step[:-2]
            nxt = cur.get(key) if isinstance(cur, dict) else (cur if isinstance(cur, list) else None)
            if not isinstance(nxt, list):
                return []
            out: list[object] = []
            for one in nxt:
                out.extend(collect(one, index + 1))
            return out
        if isinstance(cur, dict) and step in cur:
            return collect(cur[step], index + 1)
        return []

    return collect(node, 0)


def test_no_pseudex() -> list[str]:
    leaked = [name for name in sys.modules if name.split(".")[0] == "pseudex"]
    return [f"the v6 mock pulled in {leaked}"] if leaked else []


def test_every_v6_tool_renders() -> list[str]:
    problems: list[str] = []
    case = _case()
    backend = seed_backend_v6(case)
    real = {item.canonical or item.value for item in case.base.pii}
    folded_real = {value.lower() for value in real}
    digit_real = {digits_of(value) for value in real if len(digits_of(value)) >= 4}
    item_ids = {item.id for item in case.base.pii}
    rendered = {tool: form for tool, _args, form in RENDERS}
    by_name = {spec.base.name: spec for spec in TOOLS_V6}
    if set(rendered) != V6_NAMES:
        problems.append(f"RENDERS covers {sorted(V6_NAMES - set(rendered))} of the 78 tools? "
                        f"extra {sorted(set(rendered) - V6_NAMES)}")
    for tool, arguments, form in RENDERS:
        spec = by_name[tool]
        log = backend.call(tool, dict(arguments))
        if log.refusal is not None:
            problems.append(f"{tool}: refused its own fixture: {log.refusal.rule}")
            continue
        actual = backend.form_of(log.seq)
        if actual != form:
            problems.append(f"{tool}: expected form {form!r}, got {actual!r}")
            continue
        if form not in {one.form for one in spec.return_forms}:
            problems.append(f"{tool}: rendered {form!r}, which the spec does not declare")
            continue
        declared = next(one for one in spec.return_forms if one.form == form)
        body = json.loads(log.result_text)
        for path in declared.pii_paths:
            # A free_text leaf is prose carrying several values; the real values
            # are the tagged substrings in `result_spans`, not the leaf as a whole.
            if form == "free_text":
                continue
            values = _values_at(body, path)
            if not values:
                problems.append(f"{tool}: {path} renders nothing")
                continue
            for value in values:
                text = str(value)
                if not text:
                    problems.append(f"{tool}: {path} renders an empty value")
                    continue
                folded = text.lower()
                if folded not in folded_real and not (
                        len(digits_of(text)) >= 4 and digits_of(text) in digit_real):
                    problems.append(f"{tool}: {path} renders {text!r}, which is no seeded value")
        # A form that declares no PII path (a pure-OUT tool) legitimately tags
        # nothing; every form that does declare paths must tag at least one item.
        if declared.pii_paths and not log.result_spans:
            problems.append(f"{tool}: no item was tagged in the result")
        for tag, (start, end) in log.result_spans.items():
            if tag.startswith("echo:"):
                tag = tag[len("echo:"):]
            if tag not in item_ids:
                problems.append(f"{tool}: tag {tag!r} is not an item id")
            elif not log.result_text[start:end]:
                problems.append(f"{tool}: tag {tag!r} spans an empty slice")
    return problems


def test_refusal_echoes_value() -> list[str]:
    problems: list[str] = []
    backend = seed_backend_v6(_case())
    # A malformed argument is refused with the documented rule, and the message
    # names the offending value (R-18: recorded as error_with_value).
    log = backend.call("sms_send", {"destination": "89164021187", "text": "x"})
    if log.refusal is None or not log.refusal.rule:
        problems.append("a malformed destination was not refused with a rule name")
        return problems
    if backend.form_of(log.seq) != "error_with_value":
        problems.append(f"the refusal is recorded as {backend.form_of(log.seq)!r}, "
                        f"not error_with_value")
    if "89164021187" not in log.result_text:
        problems.append(f"the offending value is not echoed in the refusal: {log.result_text!r}")
    # The NEGATIVE: a well-formed call is not a refusal.
    ok = backend.call("sms_send", {"destination": PHONE, "text": "x"})
    if ok.refusal is not None:
        problems.append("a well-formed destination was refused")
    return problems


def test_one_tag_per_item() -> list[str]:
    problems: list[str] = []
    backend = seed_backend_v6(_case())
    # A result carrying several items (name + passport series/number + inn) must
    # tag each item ONCE, never twice.
    log = backend.call("cdek_order_info", {"cdek_number": "1234567890"})
    if log.refusal is not None:
        return [f"cdek_order_info refused its own fixture: {log.refusal.rule}"]
    seen: dict[str, int] = {}
    for tag in log.result_spans:
        seen[tag] = seen.get(tag, 0) + 1
    repeated = {tag: count for tag, count in seen.items() if count > 1}
    if repeated:
        problems.append(f"an item was tagged more than once: {repeated}")
    if len(seen) < 4:
        problems.append(f"expected four distinct items tagged, got {sorted(seen)}")
    # THE NEGATIVE, AT THE WRITER: the same tag twice in one node is refused —
    # this is the guarantee R-20 stands on.
    try:
        serialise({"x": [Slot("a", "i"), Slot("b", "i")]})
        problems.append("the writer accepted two slots under one tag")
    except WriterError:
        pass
    return problems


def test_no_control_chars() -> list[str]:
    problems: list[str] = []
    backend = seed_backend_v6(_case())
    # A free-text/address value with spaces (not control chars) lays its span
    # down cleanly; no control character may sit inside a slot (R-21).
    log = backend.call("marketplace_order_get", {"posting_number": "0123456789-0001-1"})
    if log.refusal is not None:
        return [f"marketplace_order_get refused its own fixture: {log.refusal.rule}"]
    for tag, (start, end) in log.result_spans.items():
        slice_text = log.result_text[start:end]
        if any(unicodedata.category(ch) == "Cc" for ch in slice_text):
            problems.append(f"slot {tag!r} carries a control character: {slice_text!r}")
    # THE NEGATIVE: a value carrying a newline cannot be laid down as a slot.
    try:
        serialise({"x": Slot("a\nb", "t")})
        problems.append("the writer accepted a control character inside a slot")
    except WriterError:
        pass
    return problems


def test_unschemed_have_no_handler() -> list[str]:
    problems: list[str] = []
    if not UNSCHEMED_NAMES:
        problems.append("UNSCHEMED_NAMES is empty")
    overlap = sorted(UNSCHEMED_NAMES & V6_NAMES)
    if overlap:
        problems.append(f"unschemed names collided with schemed ones: {overlap}")
    return problems


CHECKS = (test_no_pseudex, test_every_v6_tool_renders, test_refusal_echoes_value,
          test_one_tag_per_item, test_no_control_chars, test_unschemed_have_no_handler)


def main() -> int:
    failures = 0
    for check in CHECKS:
        for problem in check():
            print(f"FAIL {check.__name__}: {problem}")
            failures += 1
    print("test_mock_v6: PASS" if not failures else f"test_mock_v6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
