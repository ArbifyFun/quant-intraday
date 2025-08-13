import yaml
def test_portfolio_yaml():
    cfg=yaml.safe_load(open('portfolio.yaml','r',encoding='utf-8'))
    assert 'instruments' in cfg and isinstance(cfg['instruments'], list)
