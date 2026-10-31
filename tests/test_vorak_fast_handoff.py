"""Offline tests for VORAK app speed, browser reuse and manual robot checks.

Run:
python -m unittest discover -s tests -p test_vorak_fast_handoff.py -v
No real browser, microphone, network, or Windows process required.
"""
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from vorak_integrated import browser_workspace as browser
from vorak_integrated import actions
from brain import application_resolver as resolver


class FakeLocator:
    def __init__(self, page):
        self.page = page

    def count(self):
        return 0

    def inner_text(self, timeout=None):
        return self.page.body


class FakePage:
    def __init__(self, url='about:blank', body='Search the web', title='Google'):
        self.url = url
        self.body = body
        self._title = title
        self.frames = []
        self.goto_count = 0

    def title(self):
        return self._title

    def locator(self, query):
        return FakeLocator(self)

    def goto(self, url, **kwargs):
        self.goto_count += 1
        self.url = url


class BrowserTests(TestCase):
    def test_reuse_same_page_without_navigation(self):
        url='https://www.google.com/search?q=MrBeast'
        page=FakePage(url=url)
        result=browser.execute(page,'open',url=url)
        self.assertEqual(result['status'],'already_open')
        self.assertEqual(page.goto_count,0)

    def test_robot_challenge_keeps_browser_open(self):
        url='https://www.google.com/search?q=MrBeast'
        page=FakePage(url=url,body="I'm not a robot. Verify you are human.")
        result=browser.execute(page,'inspect')
        self.assertEqual(result['status'],'verification_required')
        self.assertEqual(page.url,url)
        self.assertEqual(page.goto_count,0)
        self.assertNotIn('_frame',result)

    def test_resume_after_manual_challenge(self):
        url='https://www.google.com/search?q=MrBeast'
        page=FakePage(url=url,body="I'm not a robot")
        self.assertEqual(browser.execute(page,'resume')['status'],'verification_required')
        page.body='Search results for MrBeast'
        r=browser.execute(page,'resume')
        self.assertEqual(r['status'],'ready')
        self.assertEqual(page.goto_count,0)

    def test_do_not_click_challenge_automatically(self):
        url='https://www.google.com/sorry/index'
        page=FakePage(url=url,body="I'm not a robot")
        self.assertEqual(browser.execute(page,'click',role='checkbox',name="I'm not a robot")['status'],
                         'verification_required')
        self.assertEqual(page.goto_count,0)

    def test_challenge_offers_read_only_source_fallback_not_bypass(self):
        page=FakePage(url='https://www.google.com/sorry/index',
                      body="I'm not a robot")
        result=browser.execute(page,'inspect')
        self.assertEqual(result['status'],'verification_required')
        self.assertTrue(result['requires_user_verification_for_this_page'])
        self.assertIn('current_information',result['research_alternative'])
        self.assertEqual(page.goto_count,0)

    def test_protected_pages_remain_blocked(self):
        self.assertFalse(browser.safe_url('https://www.google.com/login'))
        page=FakePage(url='https://www.google.com/login')
        r=browser.execute(page,'inspect')
        self.assertEqual(r['status'],'blocked')

    def test_plain_i_am_not_a_robot_text_detected(self):
        page=FakePage(url='https://www.google.com/search?q=MrBeast',
                      body='Please verify: I am not a robot')
        self.assertEqual(browser.execute(page,'inspect')['status'],
                         'verification_required')

    def test_robot_checkbox_is_not_automated_even_if_page_detection_misses(self):
        page=FakePage(url='https://www.google.com/search?q=MrBeast',
                      body='Ordinary results')
        r=browser.execute(page,'click',role='checkbox',name="I'm not a robot")
        self.assertEqual(r['status'],'blocked')

    def test_challenge_detection_without_credential_read(self):
        page=FakePage(url='https://www.google.com/sorry/index',body='Robot challenge')
        self.assertTrue(browser.human_verification(page))


class CacheTests(TestCase):
    def test_local_index_reused_after_restart_simulation(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=Path(folder)/'app_index_v1.json'
            apps={'calculator':{'name':'Calculator',
                 'launch_type':'app_id',
                 'launch_target':'Microsoft.WindowsCalculator_8wekyb3d8bbwe!App',
                 'normalized_name':'calculator'}}
            with mock.patch.object(resolver,'_INDEX_CACHE',cache), \
                 mock.patch.object(resolver,'_APPLICATION_INDEX',None), \
                 mock.patch.object(resolver,'build_application_index',return_value=apps) as build:
                first=resolver.get_application_index()
                self.assertEqual(first,apps)
                self.assertTrue(cache.is_file())
                resolver._APPLICATION_INDEX=None
                second=resolver.get_application_index()
                self.assertEqual(second,apps)
                build.assert_called_once()


class WebsiteDuplicateTests(TestCase):
    def test_same_url_does_not_open_duplicate_chrome_tab(self):
        with mock.patch.object(actions,'chrome_open',return_value=True) as opener:
            with mock.patch.dict(actions._RECENT_URL_OPEN,{},clear=True):
                first=actions.open_target('google')
                second=actions.open_target('google')
        self.assertEqual(first['status'],'opened')
        self.assertEqual(second['status'],'already_requested')
        opener.assert_called_once()


class LaunchTests(TestCase):
    def test_duplicate_dispatch_blocked_without_os_launch(self):
        from desktop.consequence_policy import PolicyDecision

        class FakePolicy:
            def evaluate(self, request):
                return type('Result', (), {'decision': PolicyDecision.ALLOW})()

        class FakeGate:
            calls=0
            def execute(self, request, confirmation_token=None):
                self.__class__.calls+=1
                return {'success':True}

        def fake_resolver(name):
            return {'status':'resolved','application':{
                'name':'Calculator', 'launch_type':'app_id',
                'launch_target':'Microsoft.WindowsCalculator_8wekyb3d8bbwe!App'}}

        with mock.patch('desktop.consequence_policy.ConsequencePolicy',FakePolicy):
            with mock.patch.dict(actions._RECENT_APP_DISPATCH,{},clear=True):
                r1=actions.launch_app('Calculator',resolver=fake_resolver,gate_factory=FakeGate)
                r2=actions.launch_app('Calculator',resolver=fake_resolver,gate_factory=FakeGate)
        self.assertEqual(r1['status'],'dispatched')
        self.assertEqual(r2['status'],'already_requested')
        self.assertEqual(FakeGate.calls,1)
        actions._RECENT_APP_DISPATCH.clear()


class LiveContractTests(TestCase):
    def test_live_browser_tool_supports_resume_and_preserves_voice(self):
        text=(Path(__file__).resolve().parents[1]/
              'vorak_integrated'/'live.py').read_text(encoding='utf-8')
        self.assertIn("'fill', 'resume'", text)
        self.assertIn('async with client.aio.live.connect',text)
        self.assertIn('Never solve CAPTCHAs automatically',text)
        self.assertIn('SEARCH ROUTING:',text)
        self.assertIn('current_information with kind search',text)
