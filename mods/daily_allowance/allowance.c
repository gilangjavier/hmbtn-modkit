#include "hm.h"

#define ALLOWANCE_DAILY 500

void allowance_new_day(void) {
    hm_gold_add(ALLOWANCE_DAILY);
}

void allowance_minute(void) {
    hm_gold_add(1);
}
