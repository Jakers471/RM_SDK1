# 🧪 Testing Made Simple

## The ONE Command: `./test`

That's it. Everything runs through `./test`.

### Common Tasks:

| What you want | Command |
|---------------|---------|
| Run tests | `./test` |
| See coverage | `./test view` |
| Fix failing tests | `./test failed` |
| Quick check | `./test quick` |
| Check status | `./test status` |
| See all options | `./test menu` |

### Examples:

```bash
# Most common workflow
./test          # Run everything
./test view     # See what's not covered
./test failed   # Fix the broken stuff
```

### First Time Setup:

```bash
chmod +x test   # Make it executable (only needed once)
./test          # Run!
```

That's literally all you need to know! 🎉