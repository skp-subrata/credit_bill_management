import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app import app

def run_tests():
    print("==================================================")
    print("Testing UI Theme Switcher Integration")
    print("==================================================")

    with app.test_client() as client:
        res = client.get('/login')
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert 'setAppTheme' in html
        assert 'app_theme' in html
        assert 'theme-light' in html
        assert 'theme-emerald' in html
        assert 'theme-indigo' in html
        print("  - Login page rendered with theme pre-loader, theme switcher dropdown, and CSS theme definitions.")

        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role_code'] = 'admin'

        res_dash = client.get('/')
        assert res_dash.status_code == 200
        dash_html = res_dash.get_data(as_text=True)
        assert '🎨' in dash_html
        assert 'setAppTheme(\'emerald\')' in dash_html
        print("  - Dashboard page rendered with theme selector dropdown in navigation header.")

    print("\n==================================================")
    print("ALL UI THEME SWITCHER TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
