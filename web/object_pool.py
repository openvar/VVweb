import threading
from VariantValidator import Validator

class ObjectPool:
    def __init__(self, object_type, initial_pool_size=10, max_pool_size=10):
        self.pool_size = initial_pool_size
        self.max_pool_size = max_pool_size
        self.objects = [object_type() for _ in range(initial_pool_size)]
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

    def get_object(self):
        with self.condition:
            while not self.objects:
                # Wait until an object becomes available
                self.condition.wait()
            return self.objects.pop()

    def return_object(self, obj):
        with self.condition:
            if len(self.objects) < self.max_pool_size:
                self.objects.append(obj)
                self.condition.notify()  # Notify waiting threads that an object is available


# Create shared object pools
vval_object_pool = ObjectPool(Validator, initial_pool_size=6, max_pool_size=10)
g2t_object_pool = ObjectPool(Validator, initial_pool_size=2, max_pool_size=10)
batch_object_pool = ObjectPool(Validator, initial_pool_size=5, max_pool_size=10)


# <LICENSE>
# Copyright (C) 2016-2024 VariantValidator Contributors
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
