# Docker đã phục hồi và chuyển dữ liệu sang D — 22/11/2026

Người dùng đã xác nhận sao lưu rồi chuyển data Docker sang D. Hoàn tất:

- Docker Server **28.5.1** phản hồi sau phục hồi Engine.
- Sao lưu offline **14.048.821.248 byte**, source/backup SHA256 khớp: `e64cdc0a261b14d4feb5881820fb105f207ccb6601b6b7db63507ee7d31d99e2`.
- Tạo bản hoạt động riêng trên D từ VHD đã quiesce lần tiếp theo, checksum hai đầu khớp. Khác checksum backup ban đầu vì Docker đã được khởi động giữa hai lần copy; cả hai lần source giữ nguyên size/mtime trong lúc copy.
- Dùng **NTFS directory junction**, không sửa settings Docker: đường dẫn logic `C:\Users\Admin\AppData\Local\Docker\wsl\disk` trỏ tới `D:\LUMIERE-FINAL-TEST\.local-tmp\docker-desktop-data\disk`.
- Xác minh hai đường dẫn truy cập cùng file vật lý; Docker khởi động lại và giữ nguyên **9 container IDs, 13 image IDs, 13 volume names**, tất cả vẫn ở trạng thái dừng như trước chuyển.
- Chỉ sau verification mới hash lại và xóa đúng file VHD cũ đã giữ tạm trên C; không xóa container/volume. Thu hồi **14.054.064.128 byte**, C còn **17.663.762.432 byte (~16,45 GiB)** ở mốc cleanup.
- Áp dụng ACL tương đương Docker parent gốc cho hai thư mục data/backup D, loại quyền ghi rộng kế thừa từ workspace.

Docker Dashboard có thể vẫn hiện đường dẫn C do setting logic không đổi; **dữ liệu VHD thực nằm trên D**. Đây là giải pháp junction đã kiểm chứng, không tuyên bố UI đã đổi Disk image location. Thử điều khiển GUI qua accessibility không truy cập được Settings nên không bấm mù hoặc sửa key cấu hình chưa xác minh.

## Vị trí quan trọng

| Vai trò | Đường dẫn |
|---|---|
| Data đang hoạt động | `.local-tmp/docker-desktop-data/disk/docker_data.vhdx` |
| Backup độc lập, không dùng làm disk đang chạy | `.local-tmp/docker-recovery/20261122/docker_data.before-move.vhdx` |
| Snapshot IDs trước/sau move | `.local-tmp/docker-recovery/20261122/before-state.json`, `after-state.json` |
| Settings checkpoint | `.local-tmp/docker-recovery/20261122/settings-store.before-move.json` |

**Không dọn `.local-tmp` hàng loạt.** Thư mục này giờ chứa live Docker data, backup, database test, model và source checkpoints. `.gitignore` và `.dockerignore` loại toàn bộ `.local-tmp`; không add/upload VHD hoặc backups vào Git/build context.

## Bằng chứng và code

`docker-vhd-backup-20261122.json`, `docker-vhd-relocation-copy-20261122.json`, `docker-storage-activation-20261122.json`, `docker-storage-verification-20261122.json`, `docker-storage-cleanup-20261122.json`, `docker-storage-permissions-20261122.json`.

Scripts: `backup_docker_vhd_offline.py`, `activate_docker_storage_on_d.py`, `verify_docker_storage_on_d.py`. Backup giữ read handle Windows chặn writers, từ chối Docker host/distro đang chạy và file đích/report có sẵn. Activation kiểm paths, kiểm backup/copy, chỉ rename cùng ổ C rồi tạo junction; original C giữ lại đến khi runtime verification đạt. Cleanup chỉ xóa một VHD cũ có hash đúng, không recursive delete.

Đã cần shutdown utility VM để giải phóng VHD lock; chỉ làm sau khi xác nhận distro WSL duy nhất là `docker-desktop`. Không unregister distro, không factory reset, không format. Phục hồi ban đầu/những probe timeout giữ trong `docker-recovery-actions-20261121.json` và `docker-after-host-restart-20261121.json`.

## Rollback có kiểm soát

Chỉ cân nhắc rollback snapshot ban đầu khi chưa có dữ liệu nghiệp vụ mới cần giữ. Dừng Docker và xác nhận VHD offline; copy backup sang **thư mục D mới** rồi đối chiếu checksum. Giữ nguyên disk hiện tại. Kiểm tra junction đúng loại và target trước khi đổi liên kết sang bản phục hồi; không xóa dữ liệu đích, không dùng recursive delete để gỡ junction. Khởi động và đối soát IDs/volumes/ứng dụng lại. Nếu có dữ liệu nghiệp vụ phát sinh sau snapshot thì cần backup mới và quy trình restore riêng, không ghi đè bằng snapshot cũ.

Hướng dẫn Docker chính thức: [backup yêu cầu dừng Docker Desktop](https://docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/), [vị trí dữ liệu WSL và Settings](https://docs.docker.com/desktop/features/wsl/). Việc junction/identity verification ở trên là bằng chứng vận hành local, không suy diễn thành tính năng GUI.
