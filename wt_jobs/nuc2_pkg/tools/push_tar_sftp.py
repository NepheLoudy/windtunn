# -*- coding: utf-8 -*-
"""SFTP chunked push of tar to NUC via paramiko (resumable, no shell escaping)."""
import os
import sys
import time

import paramiko

HOST = "192.168.137.28"
USER = "lenovo"
KEY = os.path.expanduser("~/.ssh/id_ed25519")
SRC = r"D:\nuc_ubuntu_baseline.tar"
RDIR = "/D:/nuc_parts"
RFINAL = "/D:/nuc_ubuntu_final.tar"
CHUNK = 256 * 1024 * 1024


def connect():
    t = paramiko.Transport((HOST, 22))
    pk = paramiko.Ed25519Key.from_private_key_file(KEY)
    t.connect(username=USER, pkey=pk)
    return paramiko.SFTPClient.from_transport(t), t


def rsize(sftp, path):
    try:
        return sftp.stat(path).st_size
    except FileNotFoundError:
        return -1


def main():
    total = os.path.getsize(SRC)
    print(f"local: {total} ({total/2**30:.2f} GB)")
    sftp, tr = connect()
    print("connected")
    try:
        try:
            sftp.mkdir(RDIR)
        except IOError:
            pass
        parts = []
        off = 0
        idx = 0
        while off < total:
            end = min(off + CHUNK, total)
            parts.append((idx, off, end))
            off = end
            idx += 1
        t0 = time.time()
        done_bytes = 0
        for idx, off, end in parts:
            rname = f"{RDIR}/p{idx:04d}"
            want = end - off
            cur = rsize(sftp, rname)
            if cur == want:
                done_bytes += want
                print(f"p{idx:04d} skip (already {want})")
                continue
            attempt = 0
            ok = False
            while attempt < 4 and not ok:
                attempt += 1
                try:
                    with open(SRC, "rb") as f, sftp.open(rname, "wb") as rf:
                        f.seek(off)
                        remain = want
                        while remain > 0:
                            buf = f.read(min(8 * 1024 * 1024, remain))
                            if not buf:
                                break
                            rf.write(buf)
                            remain -= len(buf)
                    cur = rsize(sftp, rname)
                    if cur == want:
                        done_bytes += want
                        dt = time.time() - t0
                        mbps = done_bytes / 2**20 / max(dt, 1)
                        print(f"p{idx:04d} OK {want} ({dt:.0f}s, {mbps:.0f} MB/s avg)")
                        ok = True
                    else:
                        print(f"p{idx:04d} {cur} != {want} retry {attempt}")
                except Exception as e:
                    print(f"p{idx:04d} err {e} retry {attempt}")
                    time.sleep(3)
                    try:
                        sftp.close()
                        tr.close()
                    except Exception:
                        pass
                    try:
                        sftp, tr = connect()
                    except Exception as e2:
                        print(f"reconnect fail: {e2}")
                        time.sleep(5)
            if not ok:
                print(f"FATAL p{idx:04d}")
                sys.exit(1)
        print("merging remote...")
        ch = tr.open_session()
        ch.exec_command("cmd /c \"if exist D:\\nuc_ubuntu_final.tar del D:\\nuc_ubuntu_final.tar\"")
        ch.recv_exit_status()
        names = "+".join(f"D:\\nuc_parts\\p{i:04d}" for i in range(len(parts)))
        ch = tr.open_session()
        ch.exec_command(f"cmd /c \"copy /b {names} D:\\nuc_ubuntu_final.tar\"")
        rc = ch.recv_exit_status()
        print(f"merge rc={rc}")
        fs = rsize(sftp, RFINAL)
        print(f"final {fs} / {total} -> {'MERGE_OK' if fs == total else 'MISMATCH'}")
        if fs != total:
            sys.exit(1)
        ch = tr.open_session()
        ch.exec_command("cmd /c \"rd /s /q D:\\nuc_parts\"")
        ch.recv_exit_status()
        print("cleaned, ALL DONE")
    finally:
        sftp.close()
        tr.close()


if __name__ == "__main__":
    main()
