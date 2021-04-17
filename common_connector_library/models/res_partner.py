# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import requests
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    allow_search_fiscal_based_on_origin_warehouse = fields.Boolean("Search fiscal based on origin warehouse?",
                                                                   default=False,
                                                                   help="Search fiscal position based on origin"
                                                                        "warehouse")

    def _find_partner_ept(self, vals, key_list=[], extra_domain=[]):
        """
        This function find the partner based on domain.
        This function map the keys of the key_list with the dictionary and create domain and
        if you have given the extra_domain, then it will merge with _domain (i.e _domain = _domain + extra_domain).
        @requires: vals, key_list
        @param vals: i.e {'name': 'emipro', 'street': 'address', 'street2': 'address',
        'email': 'test@test.com'...}
        @param key_list: i.e ['name', 'street', 'street2', 'email',...]
        @param extra_domain: This domain for you can pass your own custom domain.
        i.e [('name', '!=', 'test')...]
        @return: partner object or False
        Migration done by twinkalc August 2020
        """
        if key_list and vals:
            _domain = [] + extra_domain
            for key in key_list:
                if not vals.get(key):
                    continue
                if (key in vals) and isinstance(vals.get(key), str):
                    _domain.append((key, '=ilike', vals.get(key)))
                else:
                    _domain.append((key, '=', vals.get(key)))
            partner = self.search(_domain, limit=1) if _domain else False
            return partner
        return False

    def search_partner_by_email(self, email):
        """
        Usage : Search Partner by Email if not found then use =ilike operator for ignore case sensitive search
        and set limit 1 because it may possible to find multiple emails due to =ilike operator
        :param email: Email Id, Type: Char
        @Task : 166956 - Common connector changes
        @Updated By : Dipak Gogiya, 21/09/2020
        :return: res.partner()
        """
        partner = self.search([('email', '=ilike', email)], limit=1)
        return partner

    def get_country(self, country_name_or_code):
        """
            Usage : Search Country by name or code if not found then use =ilike operator for ignore case sensitive
            search and set limit 1 because it may possible to find multiple emails due to =ilike operator
            :param country_name_or_code: Country Name or Country Code, Type: Char
            @Task : 166956 - Common connector changes
            @Updated By : Dipak Gogiya, 21/09/2020
            :return: res.country()
        """
        country = self.env['res.country'].search(['|', ('code', '=ilike', country_name_or_code),
                                                  ('name', '=ilike', country_name_or_code)], limit=1)
        return country

    def create_or_update_state_ept(self, country_code, state_name_or_code, zip_code, country_obj=False):
        """
        @author : Harnisha Patel
        @last_updated_on : 4/10/2019
        Modified the below method to set state from the api of zippopotam.
        Migration done by twinkalc August 2020
        """
        if not country_obj:
            country = self.get_country(country_code)
        else:
            country = country_obj
        state = self.env['res.country.state'].search(['|', ('name', '=ilike', state_name_or_code),
                                                      ('code', '=ilike', state_name_or_code),
                                                      ('country_id', '=', country.id)], limit=1)

        if not state and zip_code:
            state = self.get_state_from_api(country_code, zip_code, country)
        return state

    def get_state_from_api(self, country_code, zip_code, country):
        """
        This method tries to find state from country and zip code from zippopotam api.
        @param country_code: Code of country.
        @param zip_code: Zip code.
        @param country: Record of Country.
        @return: Record of state if found, otherwise object.
        @author: Maulik Barad on Date 22-Oct
        """
        state_obj = state = self.env['res.country.state']
        country_obj = self.env['res.country']
        try:
            url = 'https://api.zippopotam.us/' + country_code + '/' + zip_code.split('-')[0]
            response = requests.get(url)
            response = ast.literal_eval(response.content.decode('utf-8'))
        except:
            return state_obj
        if response:
            if not country:
                self.get_country(response.get('country abbreviation'))
            if not country:
                self.get_country(response.get('country'))
            if not country:
                country = country_obj.create({'name': response.get('country'),
                                              'code': response.get('country abbreviation')})

            state = state_obj.search(['|', ('name', '=', response.get('places')[0].get('state')),
                                      ('code', '=', response.get('places')[0].get('state abbreviation')),
                                      ('country_id', '=', country.id)], limit=1)
            if not state:
                state = state_obj.create({'name': response.get('places')[0].get('state'),
                                          'code': response.get('places')[0].get('state abbreviation'),
                                          'country_id': country.id})
        return state

    @api.model
    def create(self, vals):
        """
        Inherited for calling onchange method.
        We got issue of not setting the gst_treatment field automatically of Indian accounting and same field is
        required and readonly in Sale order.
        @author: Maulik Barad on Date 17-Sep-2020.
        """
        partner = super(ResPartner, self).create(vals)
        partner._onchange_country_id()
        return partner
