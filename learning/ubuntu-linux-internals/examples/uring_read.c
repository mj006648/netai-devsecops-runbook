/*
 * 사용자가 지정한 작은 일반 파일을 io_uring으로 한 번 읽는 교육용 예제.
 * Compile 예: cc -Wall -Wextra -O2 -o /tmp/uring_read uring_read.c -luring
 * 실제 device 선택이나 system parameter 변경은 하지 않는다.
 */

#include <errno.h>
#include <fcntl.h>
#include <liburing.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

enum { QUEUE_DEPTH = 8, BUFFER_SIZE = 4096 };
static const uint64_t READ_REQUEST_ID = 101;

static void print_negative_result(const char *step, int result)
{
    int error_number = -result;
    fprintf(stderr, "%s: %s (errno=%d)\n",
            step, strerror(error_number), error_number);
}

int main(int argc, char **argv)
{
    struct io_uring ring;
    struct io_uring_sqe *sqe = NULL;
    struct io_uring_cqe *cqe = NULL;
    struct stat file_status;
    char *buffer = NULL;
    int fd = -1;
    int ring_ready = 0;
    int request_may_be_pending = 0;
    int exit_status = EXIT_FAILURE;
    int result;

    if (argc != 2) {
        fprintf(stderr, "사용법: %s <작은-일반-파일>\n", argv[0]);
        return EXIT_FAILURE;
    }

    fd = open(argv[1], O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "open: %s\n", strerror(errno));
        goto cleanup;
    }

    if (fstat(fd, &file_status) < 0) {
        fprintf(stderr, "fstat: %s\n", strerror(errno));
        goto cleanup;
    }
    if (!S_ISREG(file_status.st_mode)) {
        fprintf(stderr, "입력은 일반 파일이어야 합니다\n");
        goto cleanup;
    }

    buffer = malloc(BUFFER_SIZE);
    if (buffer == NULL) {
        fprintf(stderr, "malloc: %s\n", strerror(errno));
        goto cleanup;
    }

    result = io_uring_queue_init(QUEUE_DEPTH, &ring, 0);
    if (result < 0) {
        print_negative_result("io_uring_queue_init", result);
        goto cleanup;
    }
    ring_ready = 1;

    sqe = io_uring_get_sqe(&ring);
    if (sqe == NULL) {
        fprintf(stderr, "io_uring_get_sqe: 빈 SQE를 얻지 못했습니다\n");
        goto cleanup;
    }

    io_uring_prep_read(sqe, fd, buffer, BUFFER_SIZE, 0);
    io_uring_sqe_set_data64(sqe, READ_REQUEST_ID);

    /* 제출을 시도한 뒤에는 실제 완료가 확인될 때까지 보수적으로 수명을 유지한다. */
    request_may_be_pending = 1;
    result = io_uring_submit(&ring);
    if (result < 0) {
        print_negative_result("io_uring_submit", result);
        goto cleanup;
    }
    if (result != 1) {
        fprintf(stderr, "io_uring_submit: 1개 대신 %d개를 제출했습니다\n", result);
        goto cleanup;
    }
    do {
        result = io_uring_wait_cqe(&ring, &cqe);
    } while (result == -EINTR);

    if (result < 0) {
        print_negative_result("io_uring_wait_cqe", result);
        goto cleanup;
    }

    if (io_uring_cqe_get_data64(cqe) != READ_REQUEST_ID) {
        fprintf(stderr, "예상하지 않은 completion ID입니다\n");
        io_uring_cqe_seen(&ring, cqe);
        goto cleanup;
    }

    /* 이 예제는 one-shot READ 한 건이다. 대응 CQE는 그 request의 종료를 뜻한다. */
    request_may_be_pending = 0;

    if (cqe->res < 0) {
        print_negative_result("read completion", cqe->res);
    } else if (cqe->res == 0) {
        printf("EOF: 읽은 byte가 없습니다\n");
        exit_status = EXIT_SUCCESS;
    } else {
        printf("read completion: %d byte", cqe->res);
        if (cqe->res < BUFFER_SIZE)
            printf(" (short read)");
        printf("\n");
        exit_status = EXIT_SUCCESS;
    }

    io_uring_cqe_seen(&ring, cqe);

cleanup:
    /*
     * 제출 뒤 wait 오류처럼 completion 여부가 불확실한 경로에서도 buffer를
     * 먼저 free하지 않는다. Ring close의 취소와 모든 completion의 관찰은
     * 같은 사건이 아니다. 완료가 불확실하면 buffer를 재사용하지 않고 이
     * 단발성 process 전체를 종료한다. 장기 실행 서버는 cancel/drain이 필요하다.
     */
    if (ring_ready)
        io_uring_queue_exit(&ring);

    if (request_may_be_pending) {
        fprintf(stderr, "완료를 확인하지 못해 buffer를 재사용하지 않고 종료합니다\n");
        fflush(stderr);
        _Exit(EXIT_FAILURE);
    }

    free(buffer);

    if (fd >= 0)
        close(fd);

    return exit_status;
}
