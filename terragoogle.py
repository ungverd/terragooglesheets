import httplib2
import googleapiclient.discovery
from oauth2client.service_account import ServiceAccountCredentials
import sys

import requests
from bs4 import BeautifulSoup
from bs4 import Tag

from dataclasses import dataclass


@dataclass
class Product:
    id: str
    actual: int
    delivery: int
    prognosis: int
    prognosis_type: str
    prices_actual: dict
    prices_delivery: dict
    partnumber: str


terra_base = r"https://www.terraelectronica.ru/"
onelec_base = r'https://onelec.ru/products/'
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
    for column in columns:
        if name in column:
            i = columns.index(column)
            return i
    print("No %s column\n" % name)
    return i


def get_search_links_for_row(row: list, i_type: int, i_value: int, i_footprint: int) -> [str]:
    """
    :param row: row of spreadsheet with position data
    :param i_type: index of cell with position type
    :param i_value: index of cell with position value
    :param i_footprint:  index of cell with position footprint
    :return: searchlinks for this position
    """
    search_links = []
    if row[i_type] == 'Resistor':
        position = row[i_value] + ' ' + row[i_footprint].split('_')[1]

        #fix for terra bug for some positions, 57k ot 5k7 is not recognized, replaced by 57000 r or 5700 r
        position = position.lower()
        if 'k' in position:
            i = position.index('k')
            if i+1 < len(position) and position[i+1].isdigit():
                digit = position[i+1]
                position.replace('k', digit+'00 r')
            else:
                position.replace('k', '000 r')
        search_links = get_search_links_from_page(position)
        search_links = [link + "%26ef%255B1202026%255D%255Bvalue%255D%255B%255D%3D%25C2%25B1%2B1%2525" for link in search_links]

    if row[i_type] == 'Capacitor':
        position = row[i_value] + ' ' + row[i_footprint].split('_')[1]
        if 'u' in row[i_value] or 'n' in row[i_value]:
            search_links = get_search_links_from_page(position + ' x7r')
            search_links.extend(get_search_links_from_page(position + ' x5r'))
        else:
            #fix terra bug
            position = position.lower()
            position = position.replace('pf', ' pf')
            search_links = get_search_links_from_page(position)
    new_links = []
    for link in search_links:
        if '0603' in position:
            new_links.append(correct_link_for_0603(link))
        else:
            new_links.append(link)
    return new_links


def get_search_links_from_page(search_text) -> [str]:
    """
    function gets list of search links for selected query with "smd" in description
    :param search_text - query to search (10u 16V 0805) for example
    :return: list of links with searc results
    """
    search_query = "+".join(search_text.split())
    url = terra_base + "search?text=" + search_query
    r = requests.get(url)
    soup = BeautifulSoup(r.text)
    links = soup.find('ul', {'class': "search-list"})
    try:
        search_links = [link.contents for link in links.contents if isinstance(link, Tag)]
    except AttributeError:
        print("No search links")
        return
    real_search_links = []
    for link in search_links:
        for tag in link:
            if isinstance(tag, Tag):
                search_string = tag.contents[0]
                if 'SMD' in search_string:
                    real_search_links.append(tag.attrs['href'])
    return real_search_links


def correct_link_for_0603(link: str) -> str:
    """
    0603 cage has metric and nonmetric varieties. This function excludes metric cage
    :param link: search link
    :return: corrected link without metric 0603 (aka 0201)
    """
    query = link.split('%26')
    query = [q for q in query if '0201' not in q]
    link = '%26'.join(query)
    return link


def get_product_list(link: str) -> [str]:
    """
    function gets products ids using search link
    :param link: search link
    :return: list of product ids
    """
    url = terra_base + link
    url = url + r'&f%5Bpresent%5D=1'
    r = requests.get(url)
    soup = BeautifulSoup(r.text)
    pages = soup.findAll('li', {'class': 'waves-effect'})
    products = []
    if pages:
        for page in set(pages):
            url = terra_base + page.contents[0].attrs['href']
            r = requests.get(url)
            soup = BeautifulSoup(r.text)
            links = soup.findAll('td', {'class': 'table-item-name'})
            products.extend([link.attrs['data-code'] for link in links])
        return products
    links = soup.findAll('td', {'class': 'table-item-name'})
    products = [link.attrs['data-code'] for link in links]
    return products


def get_actual_info(product_id: str) -> (int, dict, str):
    """
    function gets actual price and quantity of product. If on demand only return 0 and {}
    :param product_id: product id
    :return: quantity, dictionary with prices, partnumber
    """
    url = terra_base + "product/" + product_id
    res = requests.get(url)
    soup = BeautifulSoup(res.text)
    actual = soup.find('div', {'class': 'box-title'})
    partnumber = soup.find('h1', {'class': 'truncate'})
    try:
        partnumber = partnumber.contents[0].split()[0]
        if actual:
            actual = [tag for tag in actual if isinstance(tag, Tag)]
            actual_quantity = int(actual[0].contents[0].replace("шт.", ""))
            price_data = [tag for tag in soup.find('span', {'class': 'prices'}) if isinstance(tag, Tag)]
            prices_actual = {}
            for price in price_data:
                prices_actual[int(price.attrs['data-count'])] = float(price.attrs['data-price'])
            return actual_quantity, prices_actual, partnumber
    except AttributeError:
        print("Error here " + product_id)
    return 0, {}, partnumber


def get_delivery_info(product_id: str) -> (int, int, str, dict):
    """
    function gets delivery data for product
    :param product_id: id of product
    :return: quantity available, number of delivery units, delivery unit: day or week, delivery prices
    """
    data = '{"jsonrpc":"2.0","method":"update_offers","params":{"code":%s},"id":"objUpdateOffers||1"}' % product_id
    response = requests.post('https://www.terraelectronica.ru/services', data=data)
    res = response.text
    # print(product_id)
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
                if "более" in prognosis:
                    prognosis = [ch for ch in list(prognosis) if ch.isdigit()]
                    prognosis = int("".join(prognosis))
                else:
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


def get_product_data(link: str, products: [Product]):
    """
    adds product data to product list
    :param link: link with product links
    :param products: list of products already got
    :return:
    """
    product_ids = get_product_list(link)
    for product_id in product_ids:
        print(product_id)
        actual, prices_actual, partnumber = get_actual_info(product_id)
        delivery, prognosis, prognosis_type, prices_delivery = get_delivery_info(product_id)
        products.append(
            Product(id=product_id, actual=actual, delivery=delivery, prices_actual=prices_actual,
                    prices_delivery=prices_delivery, prognosis=prognosis,
                    prognosis_type=prognosis_type, partnumber=partnumber))
    print("finished")
    return


def get_min_price_actual_with_quantity(products: [Product], quantity: int) -> (str, float):
    """
    gets actual offer for position witn minimal price and not less then quantity items (price must be chosen
    for required quantity)
    :param quantity: required quantity of items
    :param products: list with offers for this position
    :return: id of best offer, price of best offer
    """
    actual_prices = {}
    for product in products:
        if product.actual >= quantity:
            min_price = product.prices_actual[1]
            min_id = product.id
            min_partnumber = product.partnumber
            for q in product.prices_actual.keys():
                if q <= quantity and min_price >= product.prices_actual[q]:
                    min_price = product.prices_actual[q]
            actual_prices[product.id] = [min_price, min_partnumber]
    if actual_prices:
        for product in actual_prices.keys():
            if actual_prices[product][0] < min_price:
                min_id = product
                min_price = actual_prices[product][0]
                min_partnumber = actual_prices[product][1]
        return min_id, min_price, min_partnumber
    return "0", -1, 0


def get_min_price_quantity_data(products: [Product], quantity: int, date: int) -> (float, str, int):
    """
    get best offer for quanity units with no more then date days of delivery
    :param products: list if offers
    :param date: max days of delivery
    :param quantity: required qiantity
    :return: best price, id of best offer, days of delivery
    """
    min_id, min_price_actual, min_partnumber = get_min_price_actual_with_quantity(products, quantity)
    delivery_prices = {}
    for product in products:
        if product.delivery >= quantity:
            prognosis = product.prognosis if product.prognosis_type == "Days" else product.prognosis * 7
            if prognosis <= date:
                min_price = BIG_PRICE
                for q in product.prices_delivery.keys():
                    if q <= quantity and min_price >= product.prices_delivery[q]:
                        min_price = product.prices_delivery[q]
                        delivery_prices[product.id] = [min_price, prognosis, product.partnumber]
    if delivery_prices:
        min_delivery_price = min_price
        for product in delivery_prices.keys():
            if delivery_prices[product][0] < min_delivery_price:
                min_delivery_id = product
                min_delivery_price = delivery_prices[product][0]
                min_delivery_prognosis = delivery_prices[product][1]
                min_partnumber = delivery_prices[product][2]
    else:
        return min_price_actual, min_id, 1, 0
    if min_price == 0:
        return min_delivery_price, min_delivery_id, min_delivery_prognosis, min_partnumber
    if min_price_actual <= min_delivery_price:
        return min_price_actual, min_id, 1, min_partnumber
    else:
        return min_delivery_price, min_delivery_id, min_delivery_prognosis, min_partnumber


def get_new_row(row: list, i_url: int, i_price: int, i_pn:int,  best_price_id: str, best_price: float, comment: str, pn: str, comment_text: str) -> str:
    """

    :param row: row of table with positions
    :param i_url: index of url column
    :param i_price: index of price column
    :param i_pn: index pf partnumber column
    :param best_price_id: id of best product
    :param best_price: best price
    :param comment: string with not best price and url
    :param pn: new partnumber
    :return:
    """
    new_row = row
    length = len(row)
    tail = []
    for i in range(15-length):
        tail.append("")
    row.extend(tail)
    if i_url != -1:
        new_row[i_url] = best_price_id
    else:
        new_row[10] = best_price_id
    if i_price != -1:
        new_row[i_price] = best_price
    else:
        new_row[11] = best_price
    if comment:
        new_row[12] = comment
    new_row[i_pn] = pn
    new_row[14] = comment_text
    return new_row


def get_terra_by_pn(partnumber:str) -> (float, str):
    """
    gets data from terra by partnumber
    :param partnumber:
    :return: price, url
    """
    url = terra_base + "search?text=" + partnumber
    res = requests.get(url)
    terra_url = ""
    terra_price = 0
    if 'product' in res.url:
        terra_url = res.url
        soup = BeautifulSoup(res.text)
        tags = soup.find('div', {'class': 'fast-buy'})
        if tags:
            tag = soup.find('span', {'class': 'price-single price-active'})
            terra_price = float(tag.attrs['data-price'])
    return terra_price, terra_url


def get_onelec_pn(partnumber: str) -> (float, str):
    """
    gets url and price from onelec
    :param partnumber: partnumber of product
    :return: price, url
    """
    url = onelec_base + partnumber.lower()
    res = requests.get(url)
    onelec_url = ""
    onelec_price = 0
    if res.status_code != 404:
        onelec_url = url
        soup = BeautifulSoup(res.text)
        table = soup.find('table', {'class': "table product-offers"})
        try:
            for tag in [tag for tag in table.contents[0].contents if isinstance(tag, Tag)]:
                try:
                    delivery = int(tag.contents[0].text.split()[1])
                except ValueError:
                    continue
                if delivery <= 5 and 'по запросу' not in tag.contents[1].text:
                    price = float(
                        tag.contents[2].contents[0].contents[0]['data-price-rub'].split()[0].replace(',', '.'))
                    if onelec_price == 0:
                        onelec_price = price
                    else:
                        if price < onelec_price:
                            onelec_price = price
        except AttributeError:
            return 0, ""
    return onelec_price, onelec_url


def get_best_price_from_onelec_terra_by_pn(partnumber: str)->(float, str, str):
    """
    function gets best price from onelec and terra by partnumber and selects best
    :param partnumber: partnumber for spreadsheet
    :return: best price, best url, other url+price
    """
    terra_price, terra_url = get_terra_by_pn(partnumber)
    onelec_price, onelec_url = get_onelec_pn(partnumber)
    if terra_price < onelec_price and terra_price != 0:
        return terra_price, terra_url, onelec_url + ' ' + str(onelec_price)
    if onelec_price != 0:
        return onelec_price, onelec_url, terra_url + ' ' + str(terra_price)
    return terra_price, terra_url, onelec_url + ' ' + str(onelec_price)


def get_best_price_by_PN(value: str) -> (float, str):
    """
    function gets best price from terra searhing by PN
    :param value: value to search
    :return: price, product id
    """
    url = terra_base + "search?text=" + value
    r = requests.get(url)
    link = r.url
    products = []
    if 'catalog' not in link:
        soup = BeautifulSoup(r.text)
        links = soup.find('ul', {'class': "search-list"})
        if links:
            link = links.contents[1].contents[1].attrs['href']
            get_product_data(link, products)
    else:
        get_product_data(link.split('ru/')[1], products)
    if products:
        best_price, best_url, _, _ = get_min_price_quantity_data(products, 1, 5)
        best_url = terra_base + 'product/' + best_url
        if best_url:
            PN = get_PN_from_terra(best_url)
            price_onelec, url_onelec = get_onelec_pn(PN.lower())
            comment = ""
            if price_onelec > 0 and price_onelec < best_price:
                best_price = price_onelec
                comment = best_url
                best_url = url_onelec
        return best_price, best_url, comment
    else:
        return -1, "", ""



def get_PN_from_terra(url: str):
    """
    gets PN from terra using product linf
    :param url: link at product
    :return: Partnumber
    """
    res = requests.get(url)
    soup = BeautifulSoup(res.text)
    pn = soup.find('h1')
    return pn.contents[0].split()[0]


def main(spreadsheetId, first, last):
    """
    gets position data from spreadsheet, searches it within terraelectronica, and adds it back to spreadshhet
    :param spreadsheetId: Id of spreadsheet with data
    :param first: number of first string with data
    :param last: number of last string with data
    :return:
    """
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE,
                                                                   ['https://www.googleapis.com/auth/spreadsheets',
                                                                    'https://www.googleapis.com/auth/drive'])
    httpAuth = credentials.authorize(httplib2.Http())
    service = googleapiclient.discovery.build('sheets', 'v4', http=httpAuth)

    answer = service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range='a1:o1').execute()
    columns = answer['values'][0]
    i_type = get_index(columns, "Type")
    i_value = get_index(columns, "Value")
    i_quantity = get_index(columns, "Quantity")
    i_footprint = get_index(columns, "Footprint")
    i_partnumber = get_index(columns, "PN")
    if i_type == -1 or i_value == -1 or i_footprint == -1:
        print("Cannot procede\n")
        return
    i_url = get_index(columns, "URL")
    i_price = get_index(columns, "Price")

    answer = service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range='a%i:o%i' % (first, last)).execute()
    values = answer.get('values', [])
    for (index, row) in enumerate(values):
        search_links = get_search_links_for_row(row, i_type, i_value, i_footprint)
        if search_links:
            products = []
            for link in search_links:
                get_product_data(link, products)
            if products:
                if i_quantity == -1:
                    quantity = 1
                else:
                    try:
                        quantity = int(row[i_quantity])
                    except ValueError:
                        continue
                text_comment = "Any %s %s case %s" % (row[i_type], row[i_value], row[i_footprint].split('_')[1])
                if row[i_type] == 'Resistor':
                    text_comment += ' 1%'
                if row[i_type] == 'Capacitor':
                    text_comment += ", x5r or x7r or np0 isolator"
                best_price, best_price_id, best_price_date, best_pn = get_min_price_quantity_data(products, quantity, 5)
                new_row = get_new_row(row, i_url, i_price, i_partnumber, terra_base+r'product/'+best_price_id, best_price, "", best_pn, text_comment)
                request_body = {"valueInputOption": "RAW",
                                "data": [{"range": 'a%i:o%i' % (index+first, index+first), "values": [new_row]}]}
                request = service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheetId, body=request_body)
                _ = request.execute()

        if i_partnumber != -1 and i_partnumber < len(row):
            if row[i_partnumber]:
                best_price, best_url, comment = get_best_price_from_onelec_terra_by_pn(row[i_partnumber])
                if best_price != 0:
                    new_row = get_new_row(row, i_url, i_price, i_partnumber, best_url, best_price, comment, row[i_partnumber])
                    request_body = {"valueInputOption": "RAW",
                                    "data": [{"range": 'a%i:o%i' % (values.index(row) + first, values.index(row) + first), "values": [new_row]}]}
                    request = service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheetId, body=request_body)
                    _ = request.execute()
        if row[i_type] == 'PN':
            best_price, best_price_url, comment = get_best_price_by_PN(row[i_value])
            new_row = get_new_row(row, i_url, i_price, i_partnumber, best_price_url, best_price, comment, row[i_value], "")
            request_body = {"valueInputOption": "RAW",
                            "data": [{"range": 'a%i:o%i' % (
                                values.index(row) + first, values.index(row) + first), "values": [new_row]}]}
            request = service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheetId, body=request_body)
            _ = request.execute()


if __name__ == '__main__':
    if len(sys.argv) > 3:
        try:
            main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
        except ValueError:
            print("second and third parameters are expected to be numbers (first and last BOM string numbers")
    else:
        if len(sys.argv) == 2:
            main(sys.argv[1], 2, 100)
        else:
            print("No BOM link")
