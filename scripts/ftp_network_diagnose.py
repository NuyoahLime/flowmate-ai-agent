"""Network-only FTP diagnostic. Never downloads files (no RETR operation)."""

from __future__ import annotations

import argparse
import getpass
import sys
import time
from ftplib import FTP, all_errors


class ReportingFTP(FTP):
    """FTP client that exposes the PASV endpoint used by ftplib."""

    def makepasv(self):
        host, port = super().makepasv()
        self.pasv_endpoint = (host, port)
        return host, port


def mark(stage: str, passed: bool, detail: str = "") -> None:
    prefix = "[PASS]" if passed else "[FAIL]"
    print(f"{prefix} {stage}: {detail}".rstrip())


def main() -> int:
    parser = argparse.ArgumentParser(description="FTP network diagnostic; no file download")
    parser.add_argument("--ip", default="222.192.7.77")
    parser.add_argument("--host", default="nnu.geodata.cn")
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--directory", default="CHAP_NO2_M1K_2019_2025(nc格式)")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--user", help="FTP username (otherwise prompt)")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read one password line from stdin without printing it",
    )
    args = parser.parse_args()

    user = args.user or input("FTP username: ")
    password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("FTP password (input hidden): ")
    ftp = ReportingFTP(timeout=args.timeout)
    ftp.set_debuglevel(0)
    try:
        started = time.perf_counter()
        try:
            ftp.connect(args.ip, args.port, timeout=args.timeout)
            elapsed = time.perf_counter() - started
            mark("TCP / 220", True, f"{ftp.getwelcome().strip()} ({elapsed:.2f}s; {args.ip}:{args.port})")
        except OSError as exc:
            mark("TCP / 220", False, f"{type(exc).__name__}: {exc}")
            return 1
        except all_errors as exc:
            mark("TCP / 220", False, f"{type(exc).__name__}: {exc}")
            return 1

        try:
            response = ftp.login(user=user, passwd=password)
            mark("USER / PASS", True, response.strip())
        except all_errors as exc:
            mark("USER / PASS", False, f"{type(exc).__name__}: {exc}")
            return 2

        try:
            response = ftp.pwd()
            mark("PWD", True, response)
        except all_errors as exc:
            mark("PWD", False, f"{type(exc).__name__}: {exc}")
            return 3

        try:
            response = ftp.cwd(args.directory)
            mark("CWD", True, f"{args.directory!r}; {response.strip()}")
        except all_errors as exc:
            mark("CWD", False, f"{type(exc).__name__}: {exc}")
            return 4

        ftp.set_pasv(True)
        try:
            # NLST opens and closes only the directory data channel; it does not retrieve a file.
            names = ftp.nlst()
            endpoint = getattr(ftp, "pasv_endpoint", None)
            mark("PASV", True, f"server data endpoint={endpoint!r}")
            mark("NLST / LIST", True, f"received {len(names)} entries")
            for name in names:
                print(f"  {name}")
        except all_errors as exc:
            endpoint = getattr(ftp, "pasv_endpoint", None)
            mark("PASV / NLST", False, f"endpoint={endpoint!r}; {type(exc).__name__}: {exc}")
            return 5
        finally:
            try:
                ftp.quit()
            except all_errors:
                ftp.close()
        print("No RETR command was issued; no file was downloaded or written.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        ftp.close()
        return 130


if __name__ == "__main__":
    sys.exit(main())
