"""Diagnose the ChinaHighNO2 FTP connection without downloading files.

The control connection is made to the known real IP to avoid Fxy Fake-IP.
The FTP hostname is retained for the optional HOST command and for reporting.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from ftplib import FTP, all_errors


DEFAULT_HOST = "nnu.geodata.cn"
DEFAULT_IP = "222.192.7.77"
DEFAULT_DIRECTORY = "CHAP_NO2_M1K_2019_2025(nc格式)"


def report(stage: str, ok: bool, detail: str) -> None:
    status = "成功" if ok else "失败"
    print(f"[{status}] {stage}: {detail}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FTP connectivity diagnostic only; no files are downloaded."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--directory", default=DEFAULT_DIRECTORY)
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--user", help="FTP username; if omitted, prompt securely")
    parser.add_argument(
        "--no-host-command",
        action="store_true",
        help="Do not send optional HOST <hostname> after connecting to the IP",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    username = args.user or input("FTP username: ")
    password = getpass.getpass("FTP password (input hidden): ")
    ftp = FTP()
    ftp.set_debuglevel(0)

    print(f"目标: {args.host} ({args.ip}:{args.port}), 被动模式, 不下载文件")
    try:
        # Stage 1: TCP connection and the server's 220 welcome response.
        try:
            ftp.connect(args.ip, args.port, timeout=args.timeout)
            report("TCP/220 欢迎信息", True, ftp.getwelcome().strip())
        except (OSError, all_errors) as exc:
            report("TCP/220 欢迎信息", False, f"{type(exc).__name__}: {exc}")
            return 1

        # Keep the logical FTP host available without relying on DNS/Fake-IP.
        if not args.no_host_command:
            try:
                response = ftp.sendcmd(f"HOST {args.host}")
                report("HOST", True, response.strip())
            except all_errors as exc:
                # HOST is optional in FTP and many servers legitimately reject it.
                report("HOST", False, f"服务器不接受 HOST（继续诊断）: {type(exc).__name__}: {exc}")

        # Stage 2: authentication.
        try:
            response = ftp.login(user=username, passwd=password)
            report("USER/PASS 认证", True, response.strip())
        except all_errors as exc:
            report("USER/PASS 认证", False, f"{type(exc).__name__}: {exc}")
            return 2

        # Stage 3: enter the requested directory.
        try:
            response = ftp.cwd(args.directory)
            report("CWD 数据目录", True, f"{args.directory!r} ({response.strip()})")
        except all_errors as exc:
            report("CWD 数据目录", False, f"{args.directory!r}: {type(exc).__name__}: {exc}")
            return 3

        # Stage 4: force passive mode and issue a harmless directory transfer.
        ftp.set_pasv(True)
        report("PASV 数据通道", True, "已显式启用 Passive Mode；通过后续 NLST 验证")
        try:
            names = ftp.nlst()
            report("LIST/NLST 文件列表", True, f"收到 {len(names)} 个条目")
            if names:
                print("服务器真实文件列表:")
                for name in names:
                    print(f"  {name}")
            else:
                print("服务器返回空文件列表（目录可能为空或权限受限）。")
        except all_errors as exc:
            report("LIST/NLST 文件列表", False, f"{type(exc).__name__}: {exc}")
            return 4
        finally:
            try:
                ftp.quit()
            except all_errors:
                ftp.close()
        print("诊断完成：未执行 RETR、未创建或修改任何本地文件。")
        return 0
    except KeyboardInterrupt:
        print("\n已中断。")
        ftp.close()
        return 130


if __name__ == "__main__":
    sys.exit(main())
