import httplib2
import apiclient.discovery
from oauth2client.service_account import ServiceAccountCredentials
import sys

import requests
from bs4 import BeautifulSoup
from bs4 import Tag
from collections import namedtuple
import csv
import datetime
import sys

Product = namedtuple('Product', 'id actual delivery prognosis prognosis_type prices_actual prices_delivery partnumber')
base = "https://www.terraelectronica.ru/"
BIG_PRICE = 10000

CREDENTIALS_FILE = 'LSComponents.json'

def get_index(columns: list, name: str) -> int:
    """
    gets index of column with 'name' name or -1 if column is absent
    :param columns:
    :param name:
    :return:
    """
    i = -1
    if str in names:
        i = names.index('str')
        return i
    print("No %s column\n" % s)
    return

def  get_search_links(position: str) -> [str]:
    """
    gets search links list
    :param position: search string
    :return: search link list, quantity of position
    """
    try:
        search_links = get_search_links_from_page(search_query)
    except AttributeError:
        print("Position %s not found or only one result, check on terraelectronics" % position)
        return []
    return search_links

def correct_link_for_0603(link: str) -> str:
    """

    :param link:
    :return:
    """
    query = link.split('%26')
    query = [q for q in query if not '0201' in q]

    link = '%26'.join(query)
    return link

def get_product_list(link: str) -> [str]:
    """
    function gets products ids using search link
    :param link: search link
    :return: list of product ids
    """
    url = base + link
    r = requests.get(url)
    soup = BeautifulSoup(r.text)
    pages = soup.findAll('li', {'class': 'waves-effect'})
    products = []
    if pages:
        for page in set(pages):
            url = base + page.contents[0].attrs['href']
            r = requests.get(url)
            soup = BeautifulSoup(r.text)
            links = soup.findAll('td', {'class': 'table-item-name'})
            products.extend([link.attrs['data-code'] for link in links])
        return products
    links = soup.findAll('td', {'class': 'table-item-name'})
    products = [link.attrs['data-code'] for link in links]
    return products

def get_actual_info(product_id: str) -> (int, dict):
    """
    function gets actual price and quantity of product. If on demand only return 0 and {}
    :param product_id: product id
    :return: quantity, dictionary with prices, partnumber
    """
    url = base + "product/" + product_id
    res = requests.get(url)
    soup = BeautifulSoup(res.text)
    actual = soup.find('div', {'class': 'box-title'})
    partnumber = soup.find('h1', {'class': 'truncate'})
    partnumber = partnumber.contents[0].split()[0]
    if actual:
        actual = [tag for tag in actual if isinstance(tag, Tag)]
        actual_quantity = int(actual[0].contents[0].replace("шт.", ""))
        price_data = [tag for tag in soup.find('span', {'class': 'prices'}) if isinstance(tag, Tag)]
        prices_actual = {}
        for price in price_data:
            prices_actual[int(price.attrs['data-count'])] = float(price.attrs['data-price'])
        return actual_quantity, prices_actual, partnumber
    return 0, {}, partnumber

def get_delivery_info(product_id: str) -> (int, dict):
    """
    function gets delivery data for product
    :param product_id: id of product
    :return: quantity available, number of delivery units, delivery unit: day or week, delivery prices
    """
    data = '{"jsonrpc":"2.0","method":"update_offers","params":{"code":%s},"id":"objUpdateOffers||1"}' % product_id
    response = requests.post('https://www.terraelectronica.ru/services', data=data)
    res = response.text
    print(product_id)
    res = res.split('"best_offer":')[1]
    res = res.replace(r'\"', r'"')
    res = res.replace("\n", "")
    soup = BeautifulSoup(res)
    delivery_data = soup.find('div', {'class': 'box-title'})
    if delivery_data:
        delivery_data = [tag for tag in soup.find('div', {'class': 'box-title'}) if isinstance(tag, Tag)]
        actual = delivery_data[0]
        if 'ПОД ЗАКАЗ' in actual.contents[0]:
            quantity = actual.contents[1].contents[0]
            quantity = int(quantity.replace("шт.", ""))
            prognosis = delivery_data[1].contents[0]
            if "недел" in prognosis:
                prognosis_type = "Weeks"
                prognosis = int(prognosis.split()[2].split('-')[0])
            else:
                if "дн" in prognosis:
                    prognosis_type = "Days"
                    prognosis = int(prognosis.split()[2])
        price_data = [tag for tag in soup.find('span', {'class': 'prices'}) if isinstance(tag, Tag)]
        prices_delivery = {}
        for price in price_data:
            prices_delivery[int(price.attrs['data-count'])] = float(price.attrs['data-price'])
        return quantity, prognosis, prognosis_type, prices_delivery
    return 0, 0, None, {}


def get_min_price_quantity_data(products: [Product], quantity: int, date: int) -> (float, str, int):
    """
    get best offer for quanity units with no more then date days of delivery
    :param products: list if offers
    :param date: max days of delivery
    :param quantity: required qiantity
    :return: best price, id of best offer, days of delivery
    """
    min_id, min_price_actual = get_min_price_actual_with_quantity(products, quantity)
    delivery_prices = {}
    for product in products:
        if product.delivery >= quantity:
            prognosis = product.prognosis if product.prognosis_type == "Days" else product.prognosis * 7
            if prognosis <= date:
                min_price = BIG_PRICE
                for q in product.prices_delivery.keys():
                    if q <= quantity and min_price >= product.prices_delivery[q]:
                        min_price = product.prices_delivery[q]
                        delivery_prices[product.id] = [min_price, prognosis]
    if delivery_prices:
        min_delivery_price = min_price
        for product in delivery_prices.keys():
            if delivery_prices[product][0] < min_delivery_price:
                min_delivery_id = product
                min_delivery_price = delivery_prices[product][0]
                min_delivery_prognosis = delivery_prices[product][1]
    else:
        return min_price_actual, min_id, 1
    if min_price == 0:
        return min_delivery_price, min_delivery_id, min_delivery_prognosis
    if min_price_actual <= min_delivery_price:
        return min_price_actual, min_id, 1
    else:
        return min_delivery_price, min_delivery_id, min_delivery_prognosis



def main (spreadsheetId, first, last):
    """

    :param spreadsheetId:
    :param first:
    :param last:
    :return:
    """
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE,
                                                                   ['https://www.googleapis.com/auth/spreadsheets',
                                                                    'https://www.googleapis.com/auth/drive'])
    httpAuth = credentials.authorize(httplib2.Http())
    service = apiclient.discovery.build('sheets', 'v4', http=httpAuth)

    answer = service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range='a1:o1').execute()
    columns = answer.values[0]
    i_type = get_index(columns, "Type")
    i_value = get_index(columns, "Value")
    i_quantity = get_index(columns, "Quantity")
    i_footprint = get_index(columns, "Footprint")
    if i_type == -1 or i_value == -1 or i_footprint == -1:
        print("Cannot procede\n")
        return
    i_url = get_index(columns, "Url")
    i_price = get_index(columns, "Price")

    answer = service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range='a%i:o%i' % (first, last)).execute()
    values = answer.get('values', [])
    results = ""
    for row in values:
        position = row[i_value] + ' ' + row[i_footprint]
        if row[i_type] == 'Resistor':
            position += ' 1%'
            search_links = get_search_links(position)
        if row[i_type] == 'Capacitor':
            if 'u' or 'n' in row[i_value]:
                search_links = get_search_links(position + ' x7r')
                search_links.extend(get_search_links(position + ' x5r'))
        if search_links:
            products = []
            for link in search_links:
                if '0603' in position:
                    link = correct_link_for_0603(link)
                product_ids = get_product_list(link)
                for product_id in product_ids:
                    actual, prices_actual, partnumber = get_actual_info(product_id)
                    delivery, prognosis, prognosis_type, prices_delivery = get_delivery_info(product_id)
                    products.append(
                        Product(id=product_id, actual=actual, delivery=delivery, prices_actual=prices_actual,
                                prices_delivery=prices_delivery, prognosis=prognosis,
                                prognosis_type=prognosis_type, partnumber=partnumber))
        if i_quantity == -1:
            quantity = 1
        else :
            try:
                quantity = int(row[i_quantity])
            except ValueError:
                continue
        best_price, best_price_id, best_price_date = get_min_price_quantity_data(products, quantity, date)
        new_row = row
        if i_url != -1:
            new_row[i_url] = base+'product/' + best_price_id
        else:
            new_row[12] = base+'product/' + best_price_id
        if i_price != -1:
            new_row[i_url] = base+'product/' + best_price_id
        else:
            new_row[13] = base+'product/' + best_price_id
        results.append(new_row)
    request_body = {"valueInputOption": "RAW", "data": [{"range": 'a%i:o%i' % (first, last), "values": result}]}
    request = service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheetId, body=request_body)
    _ = request.execute()


if __name__ == '__main__':
    if len(sys.argv)>3:
        try:
            main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
        except ValueError:
            print("second and third parameters are expected to be numbers (first and last BOM string numbers")
    else:
        if len(sys.argv) == 2:
            main(sys.argv[1], 2, 100)
        else:
            print("No BOM link")
