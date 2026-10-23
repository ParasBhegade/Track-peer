const store = new Map();

module.exports = {
  getItemAsync: jest.fn(async (key) => store.get(key) || null),
  setItemAsync: jest.fn(async (key, value) => {
    store.set(key, String(value));
  }),
  deleteItemAsync: jest.fn(async (key) => {
    store.delete(key);
  }),
  getItem: jest.fn((key) => store.get(key) || null),
  setItem: jest.fn((key, value) => {
    store.set(key, String(value));
  }),
  deleteItem: jest.fn((key) => {
    store.delete(key);
  }),
  __store: store,
};
