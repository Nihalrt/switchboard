package cache

import (
	"context"
	"strconv"

	"github.com/redis/go-redis/v9"
)

// define a struct to wrap the client on redis connection. The main.go communicates with this client without having to worry about the functions
// underneath the go redis library
type Client struct {
	rdb *redis.Client
}

// returns a pointer to the struct created
// New Client opens a redis connection obj to that redis server passed in the addr field.
func NewClient(addr string) *Client {
	rdb := redis.NewClient(&redis.Options{
		Addr: addr,
	})
	return &Client{rdb: rdb}
}

func (c *Client) GetRollout(ctx context.Context, flagName string) (int, error) {
	key := "flag:" + flagName
	value, error := c.rdb.Get(ctx, key).Result()
	if error != nil {
		return 0, error
	}
	rollout, err := strconv.Atoi(value)
	if err != nil {
		return 0, err
	}
	return rollout, nil

}
