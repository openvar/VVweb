import threading
from VariantValidator import Validator

class ObjectPool:
    def __init__(self, object_type, initial_pool_size=10, max_pool_size=None, wait_timeout=30):
        self.object_type = object_type
        self.initial_pool_size = initial_pool_size
        self.wait_timeout = wait_timeout

        # Pool is permanently fixed at initial size
        self.objects = [object_type() for _ in range(initial_pool_size)]

        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

    def get_object(self):
        with self.condition:
            # Object immediately available
            if self.objects:
                return self.objects.pop()

            # Wait for a return
            waited = self.condition.wait(timeout=self.wait_timeout)

            if waited and self.objects:
                return self.objects.pop()

            # No object available after timeout
            return None

    def return_object(self, obj):
        with self.condition:
            # If object died (validator crashed internally), replace it
            if obj is None:
                new_obj = self.object_type()
                self.objects.append(new_obj)
                self.condition.notify()
                return

            # If object is alive, simply return it
            self.objects.append(obj)
            self.condition.notify()

            # If somehow pool exceeded expected size, trim it
            if len(self.objects) > self.initial_pool_size:
                self.objects = self.objects[-self.initial_pool_size:]


# Create shared object pools
vval_object_pool = ObjectPool(Validator, initial_pool_size=8, max_pool_size=10)
g2t_object_pool = ObjectPool(Validator, initial_pool_size=4, max_pool_size=10)
batch_object_pool = ObjectPool(Validator, initial_pool_size=7, max_pool_size=10)


# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>
