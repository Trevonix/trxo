from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx
import typer

from trxo.auth.on_premise import OnPremAuth
from trxo.auth.token_manager import TokenManager
from trxo.utils.config_store import ConfigStore
from trxo.utils.console import console, create_table, display_panel
from trxo.utils.git.credentials import validate_credentials
from trxo.utils.url import construct_api_url


@dataclass
class CheckResult:
    name: str
    success: bool
    detail: Optional[str] = None

    def symbol(self) -> str:
        return "✔" if self.success else "✘"

    def formatted(self) -> str:
        message = f"{self.symbol()} {self.name}"
        if self.detail:
            message = f"{message} - {self.detail}"
        return message


class StatusChecker:
    def __init__(
        self,
        project_name: str,
        config: Dict,
        no_prompt: bool = False,
    ):
        self.project_name = project_name
        self.config = config or {}
        self.no_prompt = no_prompt
        self.config_store = ConfigStore()
        self.token_manager = TokenManager(self.config_store)

        self.total_checks = 0
        self.successful_checks = 0
        self.results: List[CheckResult] = []

        self.mode = "UNKNOWN"
        self.auth_mode = "NONE"
        self.am_url = None
        self.idm_url = None
        self.aic_url = None
        self.am_token = None
        self.am_realm = "root"
        self.auth_mode_config = self.config.get("auth_mode", "service-account")

    def add_result(self, name: str, success: bool, detail: Optional[str] = None):
        self.total_checks += 1
        if success:
            self.successful_checks += 1
        self.results.append(CheckResult(name=name, success=success, detail=detail))

    def run(self) -> None:
        self.detect_mode()
        if self.mode == "git":
            self.git_validation()

        self.detect_auth_mode()

        if self.am_configured and not self.aic_configured:
            self.perform_am_checks()

        if self.idm_configured and not self.aic_configured:
            self.perform_idm_checks()

        if self.aic_configured:
            self.perform_aic_checks()

    def detect_mode(self) -> None:
        storage_mode = self.config.get("storage_mode", "git") or "git"
        mode = storage_mode.lower()
        valid = mode in {"git", "local"}
        self.mode = mode if valid else storage_mode

    def git_validation(self) -> None:
        git_creds = self.config_store.get_git_credentials(self.project_name)
        if not git_creds:
            self.add_result("Git token valid", False, "Missing git credentials")
            return

        try:
            validate_credentials(git_creds["token"], git_creds["repo_url"])
            self.add_result(
                "Git token valid",
                True,
                f"Repository access validated: {git_creds['repo_url']}",
            )
        except Exception as e:
            self.add_result("Git token valid", False, str(e))

    def detect_auth_mode(self) -> None:
        am_url = self.config.get("am_base_url")
        idm_url = self.config.get("idm_base_url")
        aic_url = self.config.get("base_url")

        self.am_url = am_url.strip("/") if isinstance(am_url, str) and am_url else None
        self.idm_url = (
            idm_url.strip("/") if isinstance(idm_url, str) and idm_url else None
        )
        self.aic_url = (
            aic_url.strip("/") if isinstance(aic_url, str) and aic_url else None
        )

        self.auth_mode = []
        if self.am_url:
            self.auth_mode.append("am")
        if self.idm_url:
            self.auth_mode.append("idm")
        if self.aic_url:
            self.auth_mode.append("aic")

        self.add_result(
            "Auth mode detected",
            bool(self.auth_mode),
            ", ".join(self.auth_mode) if self.auth_mode else "None",
        )

    def am_configured(self) -> bool:
        return bool(self.am_url)

    def idm_configured(self) -> bool:
        return bool(self.idm_url)

    def aic_configured(self) -> bool:
        return bool(self.aic_url)

    def perform_am_checks(self) -> None:
        self.check_am_url()
        self.check_am_auth()
        self.validate_am_token()

    def check_am_url(self) -> None:
        if not self.am_url:
            self.add_result("AM URL reachable", False, "No AM URL configured")
            return

        try:
            with httpx.Client(timeout=15.0, follow_redirects=False) as client:
                resp = client.get(self.am_url)

            if resp.status_code < 400:
                detail = self.am_url
                if 300 <= resp.status_code < 400:
                    location = resp.headers.get("Location", "unknown")
                    detail = f"Redirect {resp.status_code} -> {location}"
                self.add_result("AM URL reachable", True, detail)
            else:
                self.add_result(
                    "AM URL reachable",
                    False,
                    f"HTTP {resp.status_code} {resp.reason_phrase} for url {resp.url}",
                )
        except Exception as e:
            self.add_result("AM URL reachable", False, str(e))

    def check_am_auth(self) -> None:
        if self.auth_mode_config == "service-account":
            try:
                self.am_token = self.token_manager.get_token(self.project_name)
                self.add_result(
                    "AM authentication successful",
                    True,
                    "Service account token acquired",
                )
            except Exception as e:
                self.add_result("AM authentication successful", False, str(e))
            return

        username = self.config.get("onprem_username")
        realm = (self.config.get("onprem_realm") or "root").strip("/") or "root"
        password = self.config.get("onprem_password")

        if not username:
            self.add_result(
                "AM authentication successful", False, "Missing On-Prem AM username"
            )
            return

        if not password and not self.no_prompt:
            password = typer.prompt("On-Prem AM password", hide_input=True)

        if not password:
            self.add_result(
                "AM authentication successful", False, "Missing On-Prem AM password"
            )
            return

        try:
            client = OnPremAuth(base_url=self.am_url, realm=realm)
            data = client.authenticate(username=username, password=password)
            self.am_token = data.get("tokenId")
            self.add_result(
                "AM authentication successful",
                bool(self.am_token),
                (
                    "On-Prem AM credentials validated"
                    if self.am_token
                    else "No token returned"
                ),
            )
        except Exception as e:
            self.add_result("AM authentication successful", False, str(e))

    def validate_am_token(self) -> None:
        if not self.am_token:
            return

        if not self.am_url:
            return

        if self.auth_mode_config == "service-account":
            headers = {"Authorization": f"Bearer {self.am_token}"}
        else:
            headers = {"Cookie": f"iPlanetDirectoryPro={self.am_token}"}

        endpoint = construct_api_url(self.am_url, "/am/")

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(endpoint, headers=headers)
                resp.raise_for_status()
        except Exception:
            self.add_result(
                "AM token valid", False, f"Failed to validate against {self.am_url}"
            )

    def perform_idm_checks(self) -> None:
        self.check_idm_url()
        self.check_idm_access()

    def check_idm_url(self) -> None:
        if not self.idm_url:
            self.add_result("IDM URL reachable", False, "No IDM URL configured")
            return

        try:
            with httpx.Client(timeout=15.0, follow_redirects=False) as client:
                resp = client.get(self.idm_url)

            if resp.status_code < 400:
                detail = self.idm_url
                if 300 <= resp.status_code < 400:
                    location = resp.headers.get("Location", "unknown")
                    detail = f"Redirect {resp.status_code} -> {location}"
                self.add_result("IDM URL reachable", True, detail)
            else:
                self.add_result(
                    "IDM URL reachable",
                    False,
                    f"HTTP {resp.status_code} {resp.reason_phrase} for url {resp.url}",
                )
        except Exception as e:
            self.add_result("IDM URL reachable", False, str(e))

    def check_idm_access(self) -> None:
        if not self.idm_url:
            self.add_result("IDM access successful", False, "No IDM URL configured")
            return

        endpoint = construct_api_url(self.idm_url, "/openidm/info/ping")
        headers: Dict[str, str] = {}

        if self.config.get("idm_username"):
            username = self.config.get("idm_username")
            password = self.config.get("idm_password")

            if not password and not self.no_prompt:
                password = typer.prompt("On-Prem IDM password", hide_input=True)

            if not password:
                self.add_result("IDM access successful", False, "Missing IDM password")
                return

            headers = {
                "X-OpenIDM-Username": username,
                "X-OpenIDM-Password": password,
                "Content-Type": "application/json",
            }
        elif self.am_configured and self.am_token:
            if self.auth_mode_config == "service-account":
                headers = {"Authorization": f"Bearer {self.am_token}"}
            else:
                headers = {"Cookie": f"iPlanetDirectoryPro={self.am_token}"}
        else:
            # Default to admin for IDM if no explicit credentials
            username = "admin"
            password = self.config.get("idm_password")

            if not password and not self.no_prompt:
                password = typer.prompt("On-Prem IDM password", hide_input=True)

            if not password:
                self.add_result("IDM access successful", False, "Missing IDM password")
                return

            headers = {
                "X-OpenIDM-Username": username,
                "X-OpenIDM-Password": password,
                "Content-Type": "application/json",
            }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(endpoint, headers=headers)
                resp.raise_for_status()
            self.add_result(
                "IDM access successful", True, "On-Prem IDM credentials validated"
            )
        except Exception as e:
            self.add_result("IDM access successful", False, str(e))

    def perform_aic_checks(self) -> None:
        self.check_aic_url()
        self.check_aic_auth()
        self.validate_aic_token()

    def check_aic_url(self) -> None:
        if not self.aic_url:
            self.add_result("AIC URL reachable", False, "No AIC URL configured")
            return

        try:
            with httpx.Client(timeout=15.0, follow_redirects=False) as client:
                resp = client.get(self.aic_url)

            if resp.status_code < 400:
                detail = self.aic_url
                if 300 <= resp.status_code < 400:
                    location = resp.headers.get("Location", "unknown")
                    detail = f"Redirect {resp.status_code} -> {location}"
                self.add_result("AIC URL reachable", True, detail)
            else:
                self.add_result(
                    "AIC URL reachable",
                    False,
                    f"HTTP {resp.status_code} {resp.reason_phrase} for url {resp.url}",
                )
        except Exception as e:
            self.add_result("AIC URL reachable", False, str(e))

    def check_aic_auth(self) -> None:
        try:
            self.am_token = self.token_manager.get_token(self.project_name)
            self.add_result(
                "AIC authentication successful",
                True,
                "Service account token acquired",
            )
        except Exception as e:
            self.add_result("AIC authentication successful", False, str(e))

    def validate_aic_token(self) -> None:
        if not self.am_token:
            return

        headers = {"Authorization": f"Bearer {self.am_token}"}
        endpoint = construct_api_url(self.aic_url, "/am/")

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(endpoint, headers=headers)
                resp.raise_for_status()
        except Exception:
            self.add_result(
                "AIC token valid", False, f"Failed to validate against {self.aic_url}"
            )

    def display(self) -> None:
        summary = (
            f"[bold]Project:[/bold] {self.project_name}\n"
            f"[bold]Storage Mode:[/bold] {self.mode.upper() if self.mode else 'UNKNOWN'}\n"
            f"[bold]Auth Mode:[/bold] {', '.join(self.auth_mode) if self.auth_mode else 'None'}\n"
            f"[bold]Checks:[/bold] {self.successful_checks}/{self.total_checks}"
        )
        display_panel(summary, "PROJECT STATUS", "blue")

        table = create_table("Configuration checks", ["Check", "Status", "Details"])
        table.columns[1].style = "bold"
        table.columns[2].style = "white"

        for result in self.results:
            status = "[green]✔ PASS[/green]" if result.success else "[red]✘ FAIL[/red]"
            table.add_row(result.name, status, result.detail or "")

        console.print(table)

        # Show troubleshooting tips for failures
        failed_checks = [r for r in self.results if not r.success]
        if failed_checks:
            tips = []
            for result in failed_checks:
                tip = self._get_troubleshooting_tip(result.name)
                if tip:
                    tips.append(f"• {tip}")
            if tips:
                display_panel("\n".join(tips), "TROUBLESHOOTING NOTES", "yellow")

    def _get_troubleshooting_tip(self, check_name: str) -> str:
        normalized = check_name.strip().lower()

        if "git token" in normalized:
            return "Git token invalid: Run 'trxo config setup --git-token <token>'"
        if "am url" in normalized:
            return "AM URL unreachable: Verify AM base URL and server running"
        if "am authentication" in normalized:
            return "AM auth unsuccessful: Check credentials or run 'trxo config setup'"
        if "idm url" in normalized:
            return "IDM URL unreachable: Verify IDM base URL and server running"
        if "idm access" in normalized:
            return (
                "IDM access unsuccessful: Check credentials or run 'trxo config setup'"
            )
        if "aic url" in normalized:
            return "AIC URL unreachable: Verify AIC base URL and server running"
        if "aic authentication" in normalized:
            return "AIC auth unsuccessful: Check SA ID/JWK or run 'trxo config setup'"
        if "auth mode" in normalized:
            return "Auth mode not detected: Run 'trxo config setup'"
        return ""
