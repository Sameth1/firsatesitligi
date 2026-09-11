import unittest
from unittest.mock import Mock, patch

from application_links import (
    FetchResult,
    fetch_url,
    is_safe_guided_url,
    resolve_application_route,
)


def map_fetcher(pages):
    def fetch(url):
        value = pages.get(url)
        if value is None:
            return FetchResult(404, url, "")
        if isinstance(value, FetchResult):
            return value
        return FetchResult(200, url, value, "text/html")
    return fetch


class ApplicationRouteTests(unittest.TestCase):
    def test_guided_url_allows_official_detail_but_not_confusing_pages(self):
        self.assertTrue(is_safe_guided_url(
            "https://official.test/programmes/scholarship-2027"
        ))
        self.assertTrue(is_safe_guided_url(
            "https://www2.daad.de/scholarship-database/?detail=10000169"
        ))
        self.assertFalse(is_safe_guided_url("https://nasilgitmis.com/program"))
        self.assertFalse(is_safe_guided_url("https://official.test/careers"))
        self.assertFalse(is_safe_guided_url(
            "https://docs.google.com/forms/d/e/private/viewform"
        ))

    @patch("application_links.requests.get")
    @patch("application_links._public_http_url", side_effect=[True, False])
    def test_redirect_to_private_network_is_blocked(self, _public, get):
        response = Mock(status_code=302, headers={"location": "http://127.0.0.1/secret"})
        get.return_value = response

        result = fetch_url("https://public.example/start")

        self.assertIsNone(result.status)
        self.assertIn("public HTTP", result.error)
        get.assert_called_once()

    def test_follows_official_details_then_direct_apply(self):
        source = '<a href="https://official.test/program">Official website</a>'
        pages = {
            "https://official.test/program": '<a href="/apply">Apply now</a>',
            "https://official.test/apply": "<html><title>Application</title><p>Start here</p></html>",
        }

        route = resolve_application_route(
            "https://youthop.com/item", source, fetcher=map_fetcher(pages)
        )

        self.assertTrue(route.verified)
        self.assertEqual(route.details_url, "https://official.test/program")
        self.assertEqual(route.application_url, "https://official.test/apply")
        self.assertEqual(route.application_method, "portal")

    def test_official_information_page_is_not_mislabeled_as_apply(self):
        source = '<a href="https://official.test/program">Official website</a>'
        pages = {"https://official.test/program": "<p>Eligibility and programme details.</p>"}

        route = resolve_application_route(
            "https://nasilgitmis.com/item", source, fetcher=map_fetcher(pages)
        )

        self.assertFalse(route.verified)
        self.assertIsNone(route.application_url)
        self.assertEqual(route.details_url, "https://official.test/program")

    def test_apply_button_to_another_information_page_is_not_enough(self):
        source = '<a href="https://official.test/program-info">Apply now</a>'
        route = resolve_application_route(
            "https://news.test/item",
            source,
            fetcher=map_fetcher({
                "https://official.test/program-info": "<p>Programme details only.</p>"
            }),
        )
        self.assertFalse(route.verified)

    def test_how_to_apply_and_generic_register_are_not_direct_routes(self):
        source = """
          <a href="/guide">How to apply</a>
          <a href="/register">Register</a>
        """
        route = resolve_application_route(
            "https://official.test/program", source, fetcher=map_fetcher({})
        )
        self.assertFalse(route.verified)
        self.assertIsNone(route.application_url)

    def test_same_domain_apply_path_is_allowed(self):
        source = '<a href="/applications/start">Start your application</a>'
        pages = {
            "https://official.test/applications/start": "<html><title>Application portal</title></html>"
        }
        route = resolve_application_route(
            "https://official.test/program", source, fetcher=map_fetcher(pages)
        )
        self.assertTrue(route.verified)
        self.assertEqual(route.application_url, "https://official.test/applications/start")

    def test_apply_section_information_page_is_not_enough(self):
        route = resolve_application_route(
            "https://official.test/en/apply/programmes/fellowship",
            "<p>Programme information and eligibility.</p>",
            fetcher=map_fetcher({}),
        )
        self.assertFalse(route.verified)

    def test_search_form_is_not_an_application_form(self):
        source = """
          <form action="/search" method="get">
            <input type="search" name="q"><select name="country"><option>DE</option></select>
          </form>
        """
        route = resolve_application_route(
            "https://daad.test/database", source, fetcher=map_fetcher({})
        )
        self.assertFalse(route.verified)

    def test_embedded_application_form_uses_current_page(self):
        source = """
          <form action="/submit" method="post" id="application-form">
            <input name="name"><input name="email"><button>Apply</button>
          </form>
        """
        route = resolve_application_route(
            "https://official.test/apply", source, fetcher=map_fetcher({})
        )
        self.assertTrue(route.verified)
        self.assertEqual(route.application_method, "online_form")

    def test_same_page_form_anchor_is_preserved(self):
        source = '<a href="#form">Burs Başvurusu</a><a id="form"></a>'

        route = resolve_application_route(
            "https://official.test/scholarship", source, fetcher=map_fetcher({})
        )

        self.assertTrue(route.verified)
        self.assertEqual(
            route.application_url,
            "https://official.test/scholarship#form",
        )
        self.assertEqual(route.application_method, "online_form")

    def test_document_and_known_form_provider_are_actionable(self):
        pdf = '<a href="https://official.test/application.pdf">Application form</a>'
        form = '<a href="https://forms.gle/abc123">Apply here</a>'
        pdf_route = resolve_application_route(
            "https://official.test/program",
            pdf,
            fetcher=map_fetcher({
                "https://official.test/application.pdf": FetchResult(
                    200, "https://official.test/application.pdf", "", "application/pdf"
                )
            }),
        )
        form_route = resolve_application_route(
            "https://official.test/program", form, fetcher=map_fetcher({
                "https://forms.gle/abc123": "<html><title>Application form</title></html>"
            })
        )
        self.assertEqual(pdf_route.application_method, "document")
        self.assertTrue(pdf_route.verified)
        self.assertEqual(form_route.application_method, "online_form")
        self.assertTrue(form_route.verified)

    def test_turkish_click_label_to_known_form_is_actionable(self):
        source = '<a href="https://docs.google.com/forms/d/e/abc/viewform">TIKLAYINIZ</a>'
        route = resolve_application_route(
            "https://nasilgitmis.com/program", source, fetcher=map_fetcher({
                "https://docs.google.com/forms/d/e/abc/viewform": (
                    "<html><title>Application form</title></html>"
                )
            })
        )
        self.assertTrue(route.verified)
        self.assertEqual(route.application_method, "online_form")

    def test_known_form_provider_must_be_publicly_accessible(self):
        source = '<a href="https://docs.google.com/forms/d/e/private/viewform">Apply</a>'
        route = resolve_application_route(
            "https://official.test/program",
            source,
            fetcher=map_fetcher({
                "https://docs.google.com/forms/d/e/private/viewform": FetchResult(
                    401,
                    "https://docs.google.com/forms/d/e/private/viewform",
                    "",
                )
            }),
        )

        self.assertFalse(route.verified)
        self.assertIsNone(route.application_url)


if __name__ == "__main__":
    unittest.main()
