import requests
from bs4 import BeautifulSoup
from bs4 import Tag
from collections import namedtuple

Product = namedtuple('Product', 'id actual delivery prognosis prognosis_type prices_actual prices_delivery')
base = "https://www.terraelectronica.ru/"


def get_search_links_list(search_text) -> [str]:
    """
    function gets list of search links for selected query with "smd" in description
    :return:
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
    links = soup.findAll('td', {'class': 'table-item-name'})
    products = [link.attrs['data-code'] for link in links]
    return products


def get_actual_info(product_id: str) -> (int, dict):
    """
    function gets actual price and quantity of product. If on demand only return 0 and {}
    :param product_id: product id
    :return: quantity, dictionary with prices
    """
    url = base + "product/" + product_id
    res = requests.get(url)
    soup = BeautifulSoup(res.text)
    actual = soup.find('div', {'class': 'box-title'})
    if actual:
        actual = [tag for tag in actual if isinstance(tag, Tag)]
        actual_quantity = int(actual[0].contents[0].replace("шт.", ""))
        price_data = [tag for tag in soup.find('span', {'class': 'prices'}) if isinstance(tag, Tag)]
        prices_actual = {}
        for price in price_data:
            prices_actual[int(price.attrs['data-count'])] = float(price.attrs['data-price'])
        return actual_quantity, prices_actual
    return 0, {}


def get_min_price_actual(products: [Product], res_number: int) -> [str]:
    """
    gets quantity (or less) most cheap offers of actual products
    :param products: list of products
    :param res_number: quantity of products
    :return: list of cheap products
    """
    actual_products = [product for product in products if product.actual]
    actual_products.sort(key=lambda x: x.prices_actual[1])
    res = []
    for i in range(min(res_number, len(actual_products))):
        res.append(actual_products[i].id)
    return res


def get_min_price_actual_with_quantity(products: [Product], quantity: int) -> [str]:
    """

    :param products:
    :param quantity:
    :return:
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
    return 0, -1

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
                prognosis_type = "Недели"
                prognosis = int(prognosis.split()[2].split('-')[0])
            else:
                if "дн" in prognosis:
                    prognosis_type = "Дни"
                    prognosis = int(prognosis.split()[2])
        price_data = [tag for tag in soup.find('span', {'class': 'prices'}) if isinstance(tag, Tag)]
        prices_delivery = {}
        for price in price_data:
            prices_delivery[int(price.attrs['data-count'])] = float(price.attrs['data-price'])
        return quantity, prognosis, prognosis_type, prices_delivery
    return 0, 0, None, {}


def get_min_price_delivery(products: [Product], res_number: int) -> str:
    """

    :param products:
    :return:
    """
    delivery_products = [product for product in products if product.delivery and 1 in product.prices_delivery.keys()]
    delivery_products.sort(key=lambda x: x.prices_delivery[1])
    res = []
    for i in range(min(res_number, len(delivery_products))):
        res.append(delivery_products[i].id)
    return res

def get_min_price(products: [Product], res_number: int) -> str:
    """

    :param products:
    :param res_number:
    :return:
    """
    res = get_min_price_actual(products, res_number)
    res.extend(get_min_price_delivery(products, res_number))
    return res


def get_min_price_quantity_data(products: [Product], quantity: int, date: int) -> str:
    """

    :param products:
    :param date:
    :param quantity:
    :return:
    """
    min_id, min_price_actual = get_min_price_actual_with_quantity(products, quantity)
    delivery_prices = {}
    for product in products:
        if product.delivery >= quantity:
            prognosis = product.prognosis if product.prognosis_type == "Дни" else product.prognosis*7
            if (prognosis <= date):
                min_price = 10000
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


def main():
    g = open(r"C:\Users\juice\Downloads\Ostranna\Scripts\terra_results.txt", "w")
    try:
        f = open(r"C:\Users\juice\Downloads\Ostranna\Scripts\terra.txt")
    except FileNotFoundError:
        print('File with positions("terra.txt" does not exist)')
        return
    for position in f:
        g.write("%s " % position)
        data = position.split(":")
        search_query = data[0]
        if len(data)>1:
            quantity = int(data[1])
        else:
            quantity = 1
        try:
            search_links = get_search_links_list(search_query)
        except AttributeError:
            print("Position %s not found or only one result, check on terraelectronics" % position)
            continue
        products = []
        for link in search_links:
            product_ids = get_product_list(link)
            for product_id in product_ids:
                actual, prices_actual = get_actual_info(product_id)
                delivery, prognosis, prognosis_type, prices_delivery = get_delivery_info(product_id)
                products.append(Product(id=product_id, actual=actual, delivery=delivery, prices_actual=prices_actual,
                                        prices_delivery=prices_delivery, prognosis=prognosis,
                                        prognosis_type=prognosis_type))
        if quantity == 1:
            best_price_actual = get_min_price_actual(products, 1)
            for price in best_price_actual:
                g.write("Best Actual" +base + "product/" + price + '\n')
        else:
            best_price_id, best_price_actual = get_min_price_actual_with_quantity(products, quantity)
            g.write("Best Actual" + base + "product/" + best_price_id + ": " + str(best_price_actual)+'\n')
        best_price, best_price_id, best_price_date = get_min_price_quantity_data(products, quantity, 5)
        g.write("Best ever: %sproduct/%s Price: % 6.2f, delivered on: % i\n\n" % (base, best_price_id, best_price, best_price_date))
    g.close()

if __name__ == '__main__':
    main()

