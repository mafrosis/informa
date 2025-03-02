import datetime
import decimal
from unittest.mock import Mock, patch

from informa.plugins.tob import Order, Wine, extract_wines, parse_email


@patch('informa.plugins.tob.extract_wines', return_value=[])
def test_tob_parse_order_from_email_pack(mock_identify_wine, http_response):
    '''
    Ensure Order object is parsed correctly from an email for a pre-departure pack
    '''
    order = Order(
        number=21868,
        date=datetime.date(2024, 8, 2),
        total=decimal.Decimal('278.70'),
        discount=0,
        wines=[],
    )
    assert parse_email(http_response('tob_email_pack_21868')) == order


@patch('informa.plugins.tob.extract_wines', return_value=[])
def test_tob_parse_order_from_email_singles(mock_identify_wine, http_response):
    '''
    Ensure Order object is parsed correctly from an email for singles
    '''
    order = Order(
        number=23025,
        date=datetime.date(2024, 9, 20),
        total=decimal.Decimal('501.48'),
        discount=decimal.Decimal('-214.92'),
        wines=[],
    )
    assert parse_email(http_response('tob_email_singles_23025')) == order


@patch('informa.plugins.tob.extract_wines', return_value=[])
def test_tob_parse_order_from_email_mixed(mock_identify_wine, http_response):
    '''
    Ensure Order object is parsed correctly from an email for both singles and packs
    '''
    order = Order(
        number=18109,
        date=datetime.date(2024, 3, 14),
        total=decimal.Decimal('355.94'),
        discount=decimal.Decimal('-118.64'),
        wines=[],
    )
    assert parse_email(http_response('tob_email_mixed_18109')) == order


@patch('requests.get')
def test_tob_extract_wines_single(mock_requests_get, http_response):
    '''
    '''
    mock_requests_get.return_value = Mock(text=http_response('tob_site_single_23025'))
    # mock_fetch_image.return_value = img_response('wine01.jpg')

    wines = extract_wines('fakeurl')
    assert wines[0] == Wine(
        title='“Pezat” Bordeaux Supérieur 2022',
        tag='Elegant Bordeaux',
        url='fakeurl',
        price='$34.95',
        image_url='https://theotherbordeaux.com/wp-content/uploads/pezat.jpg',
    )


# @patch('informa.plugins.tob.fetch_image')
@patch('requests.get')
# def test_tob_extract_wines_pack(mock_requests_get, mock_fetch_image, http_response, img_response):
def test_tob_extract_wines_pack_1(mock_requests_get, http_response):  # , img_response):
    '''
    Test parsing a pack from order 21868 from Aug 2nd
    '''
    mock_requests_get.return_value = Mock(text=http_response('tob_site_pack_21868'))
    # mock_fetch_image.return_value = img_response('wine02.jpg')

    wines = extract_wines('fakeurl')
    assert wines == [
        Wine(tag='New season Rhône rosé.', url='fakeurl', price='22.95', image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/948a12bd-2f7f-6926-f319-5edc141e9195.jpg'),
        Wine(tag='Flamboyant Côtes-du-Rhône.', url='fakeurl', price='24.95', image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/b38738c1-3735-ce5e-49b1-cba971da8ef7.png'),
        Wine(tag='Gutsy GMS.', url='fakeurl', price='28.95', image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/ee8b14e0-76d8-baaf-45be-57a7c28b4c9a.jpg'),
        Wine(tag='Volcanic Cairanne.', url='fakeurl', price='38.95', image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/d981af8f-5a57-ba43-337c-7ce1e0c0149a.jpg'),
        Wine(tag='Shimmering Chablis.', url='fakeurl', price='39.95', image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/c975e2dc-0477-a2a6-d9a7-77c78983fadf.png'),
        Wine(tag='Sanely priced Blanc de Blancs Champagne at last!', url='fakeurl', price='69.95', image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/db655345-66f3-cf9d-eb8a-2757b93d730a.jpg')
    ]


@patch('requests.get')
def test_tob_extract_wines_pack_2(mock_requests_get, http_response):
    '''
    Test parsing a pack from order 18523 from Mar 28th
    '''
    mock_requests_get.side_effect = [
        Mock(text=http_response('tob_site_pack_18523')),
        Mock(text=http_response('tob_site_pack_18523_item_1')),
        Mock(text=http_response('tob_site_pack_18523_item_2')),
        Mock(text=http_response('tob_site_pack_18523_item_3')),
        Mock(text=http_response('tob_site_pack_18523_item_4')),
        Mock(text=http_response('tob_site_pack_18523_item_5')),
        Mock(text=http_response('tob_site_pack_18523_item_6')),
    ]

    wines = extract_wines('fakeurl')
    assert wines == [
        Wine(
            tag='Château Lapelletrie Saint-Émilion Grand Cru',
            url='https://theotherbordeaux.com/shop/red-wine/saint-emilion-grand-cru-chateau-lapelletrie-2019-janfeb24/',
            price='68.95',
            image_url='https://theotherbordeaux.com/wp-content/uploads/Lapelletrie-up.jpg',
            title='Château Lapelletrie Saint-Émilion Grand Cru 2019. NEW VINTAGE',
        ),
        Wine(
            tag='Crozes-Hermitage Shiraz “Origine” by Dom. Remizières',
            url='https://theotherbordeaux.com/shop/red-wine/marchapril24domaine-des-remizieres-origine-crozes-hermitage-red-2022-copy/',
            price='51.95',
            image_url='https://theotherbordeaux.com/wp-content/uploads/remiz-origine-up.png',
            title='#8. Domaine des Remizières “Origine” Crozes-Hermitage RED 2022. NEW VINTAGE.',
        ),
        Wine(
            tag='“L’Enclos de Virginie” Bordeaux',
            url='https://theotherbordeaux.com/shop/in-transit/lenclos-de-virginie-bordeaux-red-2020-by-jl-thunevin/',
            price='37.95',
            image_url='https://theotherbordeaux.com/wp-content/uploads/enclos-virg-up.jpg',
            title='“L’Enclos de Virginie” Bordeaux red 2020 by JL Thunevin. NEW VINTAGE'
        ),
        Wine(
            tag='Muscular Maucoil Côtes-du-Rhône Villages',
            url='https://theotherbordeaux.com/shop/red-wine/chateau-de-maucoil-cotes-du-rhone-villages-red-2022janfeb2024/',
            price='37.95',
            image_url='https://theotherbordeaux.com/wp-content/uploads/Rhône-maucoil-cdrv-up.jpg',
            title='Château Maucoil Côtes-du-Rhône Villages RED 2022. NEW VINTAGE.',
        ),
        Wine(
            tag='Vignobles des Quatre Vents “Z” Bordeaux 2020',
            url='https://theotherbordeaux.com/shop/red-wine/marchapril24rich-bordeaux-z-2020-copy/',
            price='32.95',
            image_url='https://theotherbordeaux.com/wp-content/uploads/Z19-up.png',
            title='Vignobles des Quatre Vents “Z” Bordeaux 2020.',
        ),
        Wine(
            tag='Château Haut Boutisse red 2022 from Bordeaux',
            url='https://theotherbordeaux.com/shop/red-wine/marchapril24chateau-haut-boutisse-red-2022-from-bordeaux-copy/',
            price='29.95',
            image_url='https://theotherbordeaux.com/wp-content/uploads/haut-boutisse-up.png',
            title='Château Haut-Boutisse RED 2022, Bordeaux. NEW VINTAGE.',
        ),
    ]


@patch('requests.get')
def test_tob_extract_wines_pack_3(mock_requests_get, http_response):
    '''
    Test parsing a pack from order 18109 from Mar 14th
    '''
    mock_requests_get.return_value = Mock(text=http_response('tob_site_pack_18109'))

    wines = extract_wines('fakeurl')
    assert wines == [
    ]
