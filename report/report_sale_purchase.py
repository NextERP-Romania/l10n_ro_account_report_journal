# Copyright (C) 2020 OdooERP Romania
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from copy import deepcopy
from odoo.exceptions import ValidationError

class SaleJournalReport(models.TransientModel):
    _name = "report.l10n_ro_account_report_journal.report_sale_purchase"
    _description = "Report Sale Purchase Journal"

    @api.model
    def _get_journal_invoice_domain(self, data, journal_type):
        date_from = data["form"]["date_from"]
        date_to = data["form"]["date_to"]
        company_id = data["form"]["company_id"]
        domain = [
            ("state", "=", "posted"),
            ("company_id", "=", company_id[0]),
        ]
        if journal_type == "sale":
            domain += [("move_type", "in", ["out_invoice", "out_refund", "out_receipt"])]
        elif journal_type == "purchase":
            domain += [("move_type", "in", ["in_invoice", "in_refund", "in_receipt"])]
# all invoices in selected period
        domain += ['|','&',
            ("invoice_date", ">=", date_from),
            ("invoice_date", "<=", date_to),
        ]
# vat on payment invoices: the invoices that are unpaied at start date
        domain += [('id','>','1')]


        
        return domain

    @api.model
    def _get_report_values(self, docids, data=None):
        company_id = data["form"]["company_id"]
        date_from = data["form"]["date_from"]
        date_to = data["form"]["date_to"]
        journal_type = data["form"]["journal_type"]
        domain = self._get_journal_invoice_domain(data, journal_type)
        invoices = self.env["account.move"].search(domain, order="invoice_date, name")
        show_warnings = data["form"]["show_warnings"]
        report_type_sale = journal_type == "sale"

        report_lines, totals = self.compute_report_lines(  invoices, data, show_warnings, report_type_sale)

        docargs = {
            "print_datetime": fields.datetime.now(),
            "date_from": date_from,
            "date_to": date_to,
            "show_warnings": show_warnings,
            "user": self.env.user.name,
            "company": self.env["res.company"].browse(company_id[0]),
            "lines": report_lines,
            "totals": totals,
            "report_type_sale": report_type_sale,
        }
        return docargs

    def compute_report_lines( self, invoices, data, show_warnings, report_type_sale=True ):
        """returns a list of a dictionary for table with the key as column
        and total dictionary with the sums of columns """
        # self.ensure_one()
        # find all the keys for dictionary
        # maybe posible_tags must be put manually,
        # but if so, to be the same as account.account.tag name
        if not invoices:
            return [],{}
        
        sale_and_purchase_comun_columns = { 'base_neex':{'type':'int','tags':[]},
                                           'base_exig':{'type':'int','tags':[]},
                                           'base_ded1':{'type':'int','tags':[]},
                                           'base_ded2':{'type':'int','tags':[]},
                                           'base_19':{'type':'int','tags':['-09_1 - BAZA','+09_1 - BAZA']},
                                           'base_9':{'type':'int','tags':['-10_1 - BAZA','+10_1 - BAZA']},
                                           'base_5':{'type':'int','tags':['-11_1 - BAZA','+11_1 - BAZA']},
                                           'base_0':{'type':'int','tags':['-14 - BAZA','+14 - BAZA']},

                                           'tva_neex':{'type':'int','tags':[]}, 
                                           'tva_exig':{'type':'int','tags':[]},                      
                                           'tva_19': {'type':'int','tags':['-09_1 - TVA','+09_1 - TVA']},
                                           'tva_9':{'type':'int','tags':['-10_1 - TVA','+10_1 - TVA']}, 
                                           'tva_5':{'type':'int','tags':['-11_1 - TVA','+11_1 - TVA']}, 
                                           'tva_bun':{'type':'int','tags':[]},
                                           'tva_serv':{'type':'int','tags':[]},

                                           'base_col':{'type':'int','tags':[]}, 
                                           'tva_col':{'type':'int','tags':[]},

                                           'invers':{'type':'int','tags':[]}, 
                                           'neimp':{'type':'int','tags':[]}, 
                                           'others':{'type':'int','tags':[]}, 
                                           'scutit1':{'type':'int','tags':[]}, 
                                           'scutit2':{'type':'int','tags':[]},

                                           'payments':{'type':'list','tags':[]},

                                           'warnings':{'type':'char','tags':[]}
                                           }
        sumed_columns = {
                        "total_base": ['base_19','base_9','base_5','base_0'],
                        "total_vat": ['tva_19', 'tva_9', 'tva_5', 'tva_bun','tva_serv',]}  # must be int
        all_known_tags = {}
        for k,v in sale_and_purchase_comun_columns.items():
            for tag in v['tags']:
                if tag in all_known_tags.keys():
                    raise ValidationError(f"tag {tag} exist in column {k} but also in column {all_known_tags(tag)}")
                all_known_tags[tag] = k

        empty_row = {k:0 for k in sumed_columns}
        empty_row.update( {k:0 for k,v in sale_and_purchase_comun_columns.items() if v['type']=='int' }) 
        empty_row.update( {k:'' for k,v in sale_and_purchase_comun_columns.items() if v['type']=='char' }) 
        empty_row.update( {k:[] for k,v in sale_and_purchase_comun_columns.items() if v['type']=='list' }) 
        

        sign = 1 if report_type_sale else -1
        report_lines = []
        for inv1 in invoices:
            vals = deepcopy(empty_row)
            vals["number"] = inv1.name
            vals["date"] = inv1.invoice_date
            vals["partner"] = inv1.commercial_partner_id.name #invoice_partner_display_name
            vals["vat"] = inv1.invoice_partner_display_vat
            vals["total"] = sign*(inv1.amount_total_signed)
            vals["warnings"] = ""

            for line in inv1.line_ids:
                if line.display_type in ['line_section', 'line_note']:
                    continue
                if line.account_id.code.startswith(
                    "411"
                ) or line.account_id.code.startswith("401"):
                    if vals["total"] != sign*(-line.credit + line.debit):
                        vals["warnings"] += (
                            f"The value of invoice is {vals['total']} but "
                            f"accounting account {line.account_id.code} has "
                            f"a value of  {sign*(-line.credit+line.debit)}"
                        )
                else:
                    unknown_line = True
                    if not line.tax_tag_ids:
                        vals['base_0'] += sign*(line.credit - line.debit)
                        unknown_line = False
                    else:
                        for tag in line.tax_tag_ids:
                            if tag.name in all_known_tags.keys():
                                vals[all_known_tags[tag.name]] =  sign*(line.credit - line.debit)
                                unknown_line = False
                    if  unknown_line:
                        vals['warnings'] += f"unknown report column for line {line.name} debit={line.debit} credit={line.credit};" 

            # put the aggregated values
            for key, value in sumed_columns.items():
                vals[key] = sum([vals[x] for x in value])

            report_lines += [vals]
# # print extracted               for testing
#             text=text_antet=''
#             for key,value in vals.items():
#                 if key in ['date','partner','total']:
#                     text_antet += key+':'+str(value)+','
#                 elif (type(value) is float) and value!=0:
#                     text += f"{key}:{value};"
#                 else:
#                     continue
#             print(text_antet+text)


        # make the totals dictionary for total line of table as sum of all the
        # integer/float values of vals
        int_float_keys = []
        for key, value in report_lines[0].items():
            if (type(value) is int) or (type(value) is float):
                int_float_keys.append(key)
        totals = {}
        for key in int_float_keys:
            totals[key] = round(sum([x[key] for x in report_lines]),2)
        return report_lines, totals
#line.tax_exigible=False   means  tax.tax_exigibility == 'on_payment'
