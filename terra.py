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


def get_search_links_from_page(search_text) -> [str]:
    """
    function gets list of search links for selected query with "smd" in description
    :param search_text - query to search (10u 16V 0805) for example
    :return: list of links with searc results
    """
    search_query = "+".join(search_text.split())
    url = base + "search?text=" + search_query
    r = requests.get(url)
    soup = BeautifulSoup(r.text)
    links = soup.find('ul', {'class': "search-list"})
    try:
        search_links = [link.contents for link in links.contents if isinstance(link, Tag)]
    except AttributeError:
        raise
    real_search_links = []
    for link in search_links:
        for tag in link:
            if isinstance(tag, Tag):
                search_string = tag.contents[0]
                if 'SMD' in search_string:
                    real_search_links.append(tag.attrs['href'])
    return real_search_links


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


def is_capasitorx57r(search_str: str) -> bool:
    """
    check if we look for capacitor
    :param search_str:
    :return:
    """
    if 'NP0' in search_str or 'np0' in search_str:
        return False
    if 'u' in search_str or 'n' in search_str or 'pf' in search_str or 'pF' in search_str:
        return True
    if 'пф' in search_str or 'мкф' in search_str or 'нф' in search_str:
        return True

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


def get_min_price_actual(products: [Product], res_number: int) -> [str]:
    """
    gets res_number(or less) most cheap offers of actual products
    :param products: list of products
    :param res_number: quantity of product ids
    :return: list of cheap products
    """
    actual_products = [product for product in products if product.actual]
    actual_products.sort(key=lambda x: x.prices_actual[1])
    res = []
    for i in range(min(res_number, len(actual_products))):
        res.append(actual_products[i].id)
    return res


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
            for q in product.prices_actual.keys():
                if q <= quantity and min_price >= product.prices_actual[q]:
                    min_price = product.prices_actual[q]
            actual_prices[product.id] = min_price
    if actual_prices:
        for product in actual_prices.keys():
            if actual_prices[product] < min_price:
                min_id = product
                min_price = actual_prices[product]
        return min_id, min_price
    return "0", -1


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


def get_min_price_delivery(products: [Product], res_number: int) -> [str]:
    """
    gets res_number best offers using only delivery information (not actual)
    :param products: list of offers for this position
    :param res_number number of result  links
    :return: id of offer
    """
    delivery_products = [product for product in products if product.delivery and 1 in product.prices_delivery.keys()]
    delivery_products.sort(key=lambda x: x.prices_delivery[1])
    res = [delivery_products[i].id for i in range(min(res_number, len(delivery_products)))]
    return res


def get_min_price(products: [Product], res_number: int) -> [str]:
    """
    get two best offers - actual and delivery
    :param products: list of offers
    :param res_number: number of results
    :return: list of best offers
    """
    res = get_min_price_actual(products, res_number)
    res.extend(get_min_price_delivery(products, res_number))
    return res


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

def create_csv(search_query: str, products: [Product]):
    now = datetime.datetime.now()
    filename = r"C:\Users\juice\Downloads\Ostranna\Scripts\terra\%s %d.%d.%d.csv" % (search_query.replace("\n", ""), now.day, now.month, now.year)
    with open(filename, "w", newline="") as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(["Partnumber", "days", "Type", "Quantity", "Price", "Starts..."])
        for product in products:
            for price in product.prices_actual.keys():
                row = [product.partnumber, 0, "Actual", product.actual, str(product.prices_actual[price]).replace(".", ","), price]
                writer.writerow(row)
            for price in product.prices_delivery.keys():
                row = [product.partnumber,  str(product.prognosis)+product.prognosis_type, "Delivery", product.delivery, str(product.prices_delivery[price]).replace(".", ","), price]
                writer.writerow(row)
            writer.writerow(["","","","", "", ""])
    file.close()

def get_files(filename: str):
    """
    opens files to read and write result
    :param filename: file with search strings
    :return: file to read, file to write
    """
    g = open(r"C:\Users\juice\Downloads\Ostranna\Scripts\Terra\terra_results.txt", "w")
    try:
        f = open(r"C:\Users\juice\Downloads\Ostranna\Scripts\terra\%s" % filename)
    except FileNotFoundError:
        print('File with positions("%s" does not exist)' % filename)
        raise
    return f, g

def  get_search_links(position: str) -> ([str], int):
    """
    gets search links list
    :param position: search string
    :return: search link list, quantity of position
    """
    data = position.split(":")
    search_query = data[0]
    if len(data) > 1:
        quantity = int(data[1])
    else:
        quantity = 1
    if not is_capasitorx57r(search_query):
        try:
            search_links = get_search_links_from_page(search_query)
        except AttributeError:
            print("Position %s not found or only one result, check on terraelectronics" % position)
            return [], quantity
    else:
        try:
            search_links = get_search_links_from_page(search_query + ' x5r')
        except AttributeError:
            search_links = []
        try:
            search_links.extend(get_search_links_from_page(search_query + ' x7r'))
        except AttributeError:
            pass
    return search_links, quantity

def correct_link_for_0603(link: str) -> str:
    """

    :param link:
    :return:
    """
    query = link.split('%26')
    query = [q for q in query if not '0201' in q]
    """for q in query:
        if '1201' in q:
            index = query.index(q)
    query.pop(index)"""
    link = '%26'.join(query)
    return link

def main(filename: str, date: int):

    try:
        f, g = get_files(filename)
    except FileNotFoundError:
        return

    for position in f:
        g.write("%s " % position)
        search_links, quantity = get_search_links(position)
        if not search_links:
            print("Position %s not found or only one result, check on terraelectronics" % position)
            continue
        products = []
        for link in search_links:
            if '0603' in position:
                link = correct_link_for_0603(link)
            product_ids = get_product_list(link)
            for product_id in product_ids:
                actual, prices_actual, partnumber = get_actual_info(product_id)
                delivery, prognosis, prognosis_type, prices_delivery = get_delivery_info(product_id)
                products.append(Product(id=product_id, actual=actual, delivery=delivery, prices_actual=prices_actual,
                                        prices_delivery=prices_delivery, prognosis=prognosis,
                                        prognosis_type=prognosis_type, partnumber=partnumber))
        if quantity == 1:
            best_price_actual = get_min_price_actual(products, 1)
            for price in best_price_actual:
                g.write("Best Actual: " + base + "product/" + price + '\n')
        else:
            best_price_id, best_price_actual = get_min_price_actual_with_quantity(products, quantity)
            g.write("Best Actual: " + base + "product/" + best_price_id + ": " + str(best_price_actual) + '\n')
        if date > 0:
            best_price, best_price_id, best_price_date = get_min_price_quantity_data(products, quantity, date)
            g.write("Best ever: %sproduct/%s Price: % 6.2f, delivered on: % i\n\n" % (
                base, best_price_id, best_price, best_price_date))
        create_csv(position.split(':')[0], products)
    g.close()


if __name__ == '__main__':
    if len(sys.argv)>1:
        main(sys.argv[1], int(sys.argv[2]))
    else:
        if len(sys.argv) == 1:
            main(sys.argv[1], 0)
        else:
            main("terra.txt", 0)


