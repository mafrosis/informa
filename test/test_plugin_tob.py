import datetime
import decimal
from unittest.mock import Mock, patch

from informa.plugins.tob import OrderLine, Wine, extract_wines, parse_email


@patch('requests.get')
def test_tob_extract_single_wine_23025(mock_requests_get, http_response):
    '''
    Test parsing single wine as found in 23025 (2024-09-20)
    https://theotherbordeaux.com/shop/red-wine/elegant-bordeaux-2/
    '''
    mock_requests_get.return_value = Mock(text=http_response('tob_site_single_23025'))

    wines = extract_wines('fakeurl')
    assert wines[0] == Wine(
        title='“Pezat” Bordeaux Supérieur 2022',
        tag='Elegant Bordeaux',
        url='fakeurl',
        price=decimal.Decimal('34.95'),
        image_url='https://theotherbordeaux.com/wp-content/uploads/pezat.jpg',
    )


@patch('requests.get')
def test_tob_extract_single_wine_24561(mock_requests_get, http_response):
    '''
    Test parsing single wine as found in 24561 (2024-11-17)
    https://theotherbordeaux.com/shop/pre-departure-offers/rich-red-cotes-du-rhone-fclmarch25/
    '''
    mock_requests_get.return_value = Mock(text=http_response('tob_site_single_24561'))

    wines = extract_wines('fakeurl')
    assert wines[0] == Wine(
        title='Juliette Avril Côtes du Rhône 2022',
        tag='#2. Domaine Juliette Avril Côtes-du-Rhône rouge 2022.',
        url='fakeurl',
        price=decimal.Decimal('26.95'),
        paid=decimal.Decimal('19.95'),
        image_url='https://theotherbordeaux.com/wp-content/uploads/ja-cdr-new.jpg',
    )


@patch('requests.get')
def test_tob_extract_single_wine_26876(mock_requests_get, http_response):
    '''
    Test parsing single wine as found in 26876 (2025-02-24)
    https://theotherbordeaux.com/shop/pre-departure-offers/domaine-croze-granier-lirac-sisyphe-2023/
    '''
    mock_requests_get.return_value = Mock(text=http_response('tob_site_single_26876'))

    wines = extract_wines('fakeurl')
    assert wines[0] == Wine(
        title='Domaine Croze-Granier Lirac “Sisyphe” 2023',
        tag='Due to low stock, this wine can only now be ordered in the Early-Winter Mixed 6-pack (click here to order it), where there is one bottle of it in each Mixed 6-pack. I apologise for any disappointment this may cause and I will be looking to get in another – bigger – shipment of this wine later in the year. I had underestimated how popular it would be.',
        url='fakeurl',
        price=decimal.Decimal('47.95'),
        paid=decimal.Decimal('34.95'),
        image_url='https://theotherbordeaux.com/wp-content/uploads/cg-lirac.jpg',
    )


@patch('requests.get')
def test_tob_extract_wines_25751(mock_requests_get, http_response):
    '''
    Test parsing a ready-to-ship mixed 6 pack in 25751 (2024-12-31)
    https://theotherbordeaux.com/shop/mixed-selections/summer-essentials-6-pack-30-off/
    '''
    mock_requests_get.side_effect = [
        Mock(text=http_response('tob_site_pack_25751')),
        Mock(text=http_response('tob_site_pack_25751_item_1')),
        Mock(text=http_response('tob_site_pack_25751_item_2')),
        Mock(text=http_response('tob_site_pack_25751_item_3')),
        Mock(text=http_response('tob_site_pack_25751_item_4')),
        Mock(text=http_response('tob_site_pack_25751_item_5')),
        Mock(text=http_response('tob_site_pack_25751_item_6')),
    ]

    wines = extract_wines('fakeurl', OrderLine(decimal.Decimal('236.34'), 6))
    assert wines == [
        Wine(tag='Premier Cru Complexity', url='https://theotherbordeaux.com/shop/white-wine/champagne-veuve-maitre-geoffroy-pulsation-premier-cru-brut-nv/',
             price=decimal.Decimal('94.95'), paid=decimal.Decimal('66.45'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/vmg1er-high-definition-.jpg', title='Champagne Veuve Maître Geoffroy “Pulsation” Premier Cru Brut NV.'),
        Wine(tag='Yours Sancerre-ly!', url='https://theotherbordeaux.com/shop/white-wine/novdec24domaine-des-cotes-blanches-sancerre-blanc-2023/',
             price=decimal.Decimal('67.95'), paid=decimal.Decimal('47.55'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/millet-sancerre.png', title='Domaine des Côtes Blanches Sancerre Blanc 2023. NEW vintage.'),
        Wine(tag='Saint-Émilion Grand Cru', url='https://theotherbordeaux.com/shop/red-wine/la-reserve-de-chateau-palais-cardinal-saint-emilion-grand-cru-2022/',
             price=decimal.Decimal('53.95'), paid=decimal.Decimal('37.76'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/palais-cardinal-reserve-up-1.jpg', title='La Réserve de Château Palais Cardinal, Saint-Émilion Grand Cru 2022. New vintage.'),
        Wine(tag='Burgundy Brut', url='https://theotherbordeaux.com/shop/white-wine/moingeon-2022-sparkling-brut-from-burgundy/',
             price=decimal.Decimal('48.95'), paid=decimal.Decimal('34.26'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/bbb-moingeon-up.png', title='Moingeon 2022 Sparkling Brut from Burgundy. New vintage.'),
        Wine(tag='V-V-V Vouvray', url='https://theotherbordeaux.com/shop/white-wine/vieux-vauvert-vouvray-2023/',
             price=decimal.Decimal('37.95'), paid=decimal.Decimal('26.56'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/vieux-vauvert-up.jpg', title='Vieux Vauvert Vouvray 2023. New vintage.'),
        Wine(tag='Bordeaux Supérieur for Summer', url='https://theotherbordeaux.com/shop/red-wine/chateau-haut-boutisse-bordeaux-superieur-2023/',
             price=decimal.Decimal('33.95'), paid=decimal.Decimal('23.76'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/haut-boutisse-up.png', title='Château Haut-Boutisse Bordeaux Supérieur 2023. New vintage.'),
    ]


@patch('requests.get')
def test_tob_extract_wines_18523(mock_requests_get, http_response):
    '''
    Test parsing a ready-to-ship mixed 6 pack in order 18523 (2024-03-28)
    https://theotherbordeaux.com/shop/red-wine/all-reds-mixed-6-pack-special-20-off/
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

    wines = extract_wines('fakeurl', OrderLine(decimal.Decimal('415.44'), 12))
    assert wines == [
        Wine(tag='Château Lapelletrie Saint-Émilion Grand Cru', url='https://theotherbordeaux.com/shop/red-wine/saint-emilion-grand-cru-chateau-lapelletrie-2019-janfeb24/',
             price=decimal.Decimal('68.95'), paid=decimal.Decimal('55.15'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/Lapelletrie-up.jpg', title='Château Lapelletrie Saint-Émilion Grand Cru 2019. NEW VINTAGE'),
        Wine(tag='Crozes-Hermitage Shiraz “Origine” by Dom. Remizières', url='https://theotherbordeaux.com/shop/red-wine/marchapril24domaine-des-remizieres-origine-crozes-hermitage-red-2022-copy/',
             price=decimal.Decimal('51.95'), paid=decimal.Decimal('41.55'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/remiz-origine-up.png', title='#8. Domaine des Remizières “Origine” Crozes-Hermitage RED 2022. NEW VINTAGE.'),
        Wine(tag='“L’Enclos de Virginie” Bordeaux', url='https://theotherbordeaux.com/shop/in-transit/lenclos-de-virginie-bordeaux-red-2020-by-jl-thunevin/',
             price=decimal.Decimal('37.95'), paid=decimal.Decimal('30.35'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/enclos-virg-up.jpg', title='“L’Enclos de Virginie” Bordeaux red 2020 by JL Thunevin. NEW VINTAGE'),
        Wine(tag='Muscular Maucoil Côtes-du-Rhône Villages', url='https://theotherbordeaux.com/shop/red-wine/chateau-de-maucoil-cotes-du-rhone-villages-red-2022janfeb2024/',
             price=decimal.Decimal('37.95'), paid=decimal.Decimal('30.35'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/Rhône-maucoil-cdrv-up.jpg', title='Château Maucoil Côtes-du-Rhône Villages RED 2022. NEW VINTAGE.'),
        Wine(tag='Vignobles des Quatre Vents “Z” Bordeaux 2020', url='https://theotherbordeaux.com/shop/red-wine/marchapril24rich-bordeaux-z-2020-copy/',
             price=decimal.Decimal('32.95'), paid=decimal.Decimal('26.35'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/Z19-up.png', title='Vignobles des Quatre Vents “Z” Bordeaux 2020.'),
        Wine(tag='Château Haut Boutisse red 2022 from Bordeaux', url='https://theotherbordeaux.com/shop/red-wine/marchapril24chateau-haut-boutisse-red-2022-from-bordeaux-copy/',
             price=decimal.Decimal('29.95'), paid=decimal.Decimal('23.96'),
             image_url='https://theotherbordeaux.com/wp-content/uploads/haut-boutisse-up.png', title='Château Haut-Boutisse RED 2022, Bordeaux. NEW VINTAGE.'),
    ]


@patch('requests.get')
def test_tob_extract_wines_21867(mock_requests_get, http_response):
    '''
    Test parsing a ready-to-ship mixed 6 pack in 21867 (2024-08-02)
    https://theotherbordeaux.com/shop/uncategorised/your-late-spring-mixed-six-burgundy-sancerre-chateauneuf-du-pape/
    '''
    mock_requests_get.side_effect = [
        Mock(text=http_response('tob_site_pack_21867')),
    ]

    wines = extract_wines('fakeurl', decimal.Decimal('278.70'))
    assert wines == [
        Wine(tag='New Vintage Côtes-du-Rhône Villages', url='fakeurl',
             price=decimal.Decimal('40.95'), paid=decimal.Decimal('29.95'),
             image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/f250265a-83bb-5cf1-c8ba-b6d182a36754.jpg'),
        Wine(tag='Burgundy Blanc de Blancs', url='fakeurl',
             price=decimal.Decimal('53.95'), paid=decimal.Decimal('39.95'),
             image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/01c432a9-777f-fa45-1435-988df1d1f093.jpg'),
        Wine(tag='The Dark Side of Sancerre', url='fakeurl',
             price=decimal.Decimal('67.95'), paid=decimal.Decimal('49.95'),
             image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/0f6e2a43-528f-3047-c0bb-d31118ab4e18.png'),
        Wine(tag='New Vintage Sancerre', url='fakeurl',
             price=decimal.Decimal('67.95'), paid=decimal.Decimal('49.95'),
             image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/28253878-4d69-d5b0-77fe-0d398d869931.png'),
        Wine(tag='Premier Cru White Burgundy', url='fakeurl',
             price=decimal.Decimal('80.95'), paid=decimal.Decimal('59.95'),
             image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/7c6b49c6-7684-02bc-6ae5-e69e4073d04e.jpg'),
        Wine(tag='Full throttle CNDP', url='fakeurl',
             price=decimal.Decimal('107.95'), paid=decimal.Decimal('79.95'),
             image_url='https://mcusercontent.com/1df7f0c4203a2fe37d91154b0/images/553f8420-7a8a-938c-1ce7-9116ac26e93e.png'),
    ]


@patch('informa.plugins.tob.extract_wines')
def test_tob_parse_email_18260(mock_extract_wines, http_response):
    '''
    Test parsing pre-departure singles email, order 18260 (2024-03-20)
    '''
    mock_extract_wines.side_effect = (
        [Wine(tag='White Burgundy: Berthenet “Tête de Cuvée” (100% Chardonnay)', price=decimal.Decimal('59.95'), title='Domaine Berthenet Montagny “Tête de Cuvée” 2022.')],
        [Wine(tag='Red Burgundy: Domaine Berthenet Pinot Noir', price=decimal.Decimal('51.95'), title='Domaine Berthenet Bourgogne Rouge Pinot Noir 2022.')],
        [Wine(tag='Shiraz blend: Château Lastours “Tradition” Gaillac red 2020', price=decimal.Decimal('28.95'), title='Château Lastours “Tradition”, red wine from Gaillac (between Bordeaux and the Med’) from vintage 2020. NEW vintage.')],
        [Wine(tag='Pure Merlot: Château Pithivier Bordeaux 2020', price=decimal.Decimal('25.95'), title='Château Pithivier Bordeaux red.')],
    )

    order = parse_email(http_response('tob_email_18260'))

    assert order.number == 18260
    assert order.date == datetime.date(2024, 3, 20)
    assert order.total == decimal.Decimal('168.70')
    assert order.discount == 0
    assert order.wines[0].paid is not None and order.wines[0].paid > 0
    assert divmod(sum([w.paid for w in order.wines]), 1)[0] == decimal.Decimal(168)


@patch('informa.plugins.tob.extract_wines')
def test_tob_parse_email_25751(mock_extract_wines, http_response):
    '''
    Test parsing pre-departure singles email, order 25751 (2024-12-31)
    '''
    mock_extract_wines.return_value = (
        [
            Wine(tag='Premier Cru Complexity', title='Champagne Veuve Maître Geoffroy “Pulsation” Premier Cru Brut NV.',
                 price=decimal.Decimal('94.95'), paid=decimal.Decimal('66.45')),
            Wine(tag='Yours Sancerre-ly!', title='Domaine des Côtes Blanches Sancerre Blanc 2023. NEW vintage.',
                 price=decimal.Decimal('67.95'), paid=decimal.Decimal('47.55')),
            Wine(tag='Saint-Émilion Grand Cru', title='La Réserve de Château Palais Cardinal, Saint-Émilion Grand Cru 2022. New vintage.',
                 price=decimal.Decimal('53.95'), paid=decimal.Decimal('37.76')),
            Wine(tag='Burgundy Brut', title='Moingeon 2022 Sparkling Brut from Burgundy. New vintage.',
                 price=decimal.Decimal('48.95'), paid=decimal.Decimal('34.26')),
            Wine(tag='V-V-V Vouvray', title='Vieux Vauvert Vouvray 2023. New vintage.',
                 price=decimal.Decimal('37.95'), paid=decimal.Decimal('26.56')),
            Wine(tag='Bordeaux Supérieur for Summer', title='Château Haut-Boutisse Bordeaux Supérieur 2023. New vintage.',
                 price=decimal.Decimal('33.95'), paid=decimal.Decimal('23.76')),
        ]
    )

    order = parse_email(http_response('tob_email_25751'))

    assert order.number == 25751
    assert order.date == datetime.date(2024, 12, 31)
    assert order.total == decimal.Decimal('236.34')
    assert order.discount == 0
    assert order.wines[0].paid is not None and order.wines[0].paid > 0
    assert divmod(sum([w.paid for w in order.wines]), 1)[0] == decimal.Decimal(236)


@patch('informa.plugins.tob.extract_wines')
def test_tob_parse_email_20405(mock_extract_wines, http_response):
    '''
    Test parsing double pack email with fixed discount, order 20405 (2024-06-09)
    '''
    mock_extract_wines.return_value = (
        [
            Wine(tag='Swaggering Côtes du Rhône', price=decimal.Decimal('32.95'), paid=decimal.Decimal('23.95')),
            Wine(tag='Rampant Roussillon red', price=decimal.Decimal('35.95'), paid=decimal.Decimal('25.95')),
            Wine(tag='Burgundian Chardonnay', price=decimal.Decimal('40.95'), paid=decimal.Decimal('29.95')),
            Wine(tag='Sancerre first, Sauvignon second', price=decimal.Decimal('64.95'), paid=decimal.Decimal('47.95')),
            Wine(tag='Artisan Châteauneuf du Pape', price=decimal.Decimal('80.95'), paid=decimal.Decimal('59.95')),
            Wine(tag='Valandraud Saint-Émilion Grand Cru', price=decimal.Decimal('94.95'), paid=decimal.Decimal('69.95')),
            Wine(tag='Swaggering Côtes du Rhône', price=decimal.Decimal('32.95'), paid=decimal.Decimal('23.95')),
            Wine(tag='Rampant Roussillon red', price=decimal.Decimal('35.95'), paid=decimal.Decimal('25.95')),
            Wine(tag='Burgundian Chardonnay', price=decimal.Decimal('40.95'), paid=decimal.Decimal('29.95')),
            Wine(tag='Sancerre first, Sauvignon second', price=decimal.Decimal('64.95'), paid=decimal.Decimal('47.95')),
            Wine(tag='Artisan Châteauneuf du Pape', price=decimal.Decimal('80.95'), paid=decimal.Decimal('59.95')),
            Wine(tag='Valandraud Saint-Émilion Grand Cru', price=decimal.Decimal('94.95'), paid=decimal.Decimal('69.95')),
        ]
    )

    order = parse_email(http_response('tob_email_20405'))

    assert order.number == 20405
    assert order.date == datetime.date(2024, 6, 9)
    assert order.total == decimal.Decimal('465.40')
    assert order.discount == decimal.Decimal(50)
    assert order.wines[0].paid is not None and order.wines[0].paid > 0
    assert divmod(sum([w.paid for w in order.wines]), 1)[0] == decimal.Decimal(465)
